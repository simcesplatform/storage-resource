# -*- coding: utf-8 -*-
# Copyright 2021 Tampere University and VTT Technical Research Centre of Finland
# This software was developed as a part of the ProCemPlus project: https://www.senecc.fi/projects/procemplus
# This source code is licensed under the MIT license. See LICENSE in the repository root directory.
# Author(s): Otto Hylli <otto.hylli@tuni.fi>
#            Antti Keski-Koukkari <antti.keski-koukkari@vtt.fi>

'''
Contains class for a simulation platform component used to simulate energy storages.
'''
import asyncio
from typing import Union, Any

from tools.components import AbstractSimulationComponent
from tools.messages import BaseMessage, AbstractResultMessage
from tools.tools import FullLogger, load_environmental_variables, EnvironmentVariable
from tools.datetime_tools import to_utc_datetime_object
from domain_messages.resource import ResourceStateMessage
from domain_messages.ControlState import ControlStatePowerSetpointMessage

from domain_tools.resource.resource_state_source import ResourceState, CsvFileResourceStateSource, CsvFileError
from storage_resource.state import StorageState

# names of used environment variables
RESOURCE_STATE_TOPIC = "RESOURCE_STATE_TOPIC"
RESOURCE_STATE_CSV_FILE = "RESOURCE_STATE_CSV_FILE"
RESOURCE_STATE_CSV_DELIMITER = "RESOURCE_STATE_CSV_DELIMITER"
CUSTOMER_ID = 'CUSTOMER_ID'
NODE = 'NODE'
CHARGE_RATE = 'CHARGE_RATE'
DISCHARGE_RATE = 'DISCHARGE_RATE'
INITIAL_STATE_OF_CHARGE = 'INITIAL_STATE_OF_CHARGE'
KWH_RATED = 'KWH_RATED'
DISCHARGE_EFFICIENCY = 'DISCHARGE_EFFICIENCY'
CHARGE_EFFICIENCY = 'CHARGE_EFFICIENCY'
KW_RATED = 'KW_RATED' 
SELF_DISCHARGE = 'SELF_DISCHARGE'
CONTROLLER_ID = 'CONTROLLER_ID'
CONTROL_STATE_TOPIC = 'CONTROL_STATE_TOPIC'

LOGGER = FullLogger( __name__ )

class StorageResource(AbstractSimulationComponent):
    '''
    A simulation platform component used to simulate energy storages. For each epoch it gets the power required from it from either a csv file or from a ControlState message.
    It calculates its state based on the power and epoch length. Then it publishes its state as a ResourceState message which
    includes the actual power the storage could manage and its state of charge.
    '''

    def __init__(self, storage: StorageState, state_source: CsvFileResourceStateSource = None, initialization_error: str = None ):
        '''
        Create a storage resource.
        storage: Used to model and calculate the actual state of the storage.
        state_source: If not None this storage will operate according to the power values from the given source. If None expects to get ControlState messages.
        initialization_error: If not None indicates that the component cannot function properly and it should send an error message with the given error message when the simulation starts.
        '''
        super().__init__()
        self._storage = storage
        self._state_source = state_source
        self.initialization_error = initialization_error
            
        if self.initialization_error is not None:
            LOGGER.error( self.initialization_error )

        # get used main topics from environment or use defaults.
        environment = load_environmental_variables(
            (RESOURCE_STATE_TOPIC, str, "ResourceState"),
            (CONTROL_STATE_TOPIC, str, 'ControlState.PowerSetpoint' )
            )
        # used as a part of the topic ResourceState messages are published to. 
        self._type = 'Storage'
        self._resource_state_topic = environment[ RESOURCE_STATE_TOPIC ]
        # publish resource states to this topic
        self._result_topic = '.'.join( [ self._resource_state_topic, self._type, self.component_name ])
        
        # other topics component listens to. Possibly the ControlState topic.
        other_topics = []
        if state_source is None:
            # no csv file subscribe to ControlState messages
            control_state_topic = environment[ CONTROL_STATE_TOPIC ]
            control_state_topic = control_state_topic +'.' +self.component_name
            other_topics = [ control_state_topic ]
            LOGGER.info(f'Listening to control state messages from topic {control_state_topic}.')
            
        else:
            LOGGER.info('Using a CSV file as the control state source.')
        
        # super class will handle subscribing to the topic.    
        self._other_topics = other_topics
        
        # store ControlState message for current epoch here.
        self._control_state_for_epoch = None

    async def process_epoch(self) -> bool:
        '''
        Handles the processing of an epoch by calculating the new state for the storage and publishing it for the epoch.
        '''
        LOGGER.debug( f'Starting to process epoch {self._latest_epoch}.' )
        try:
            await self._send_resource_state_message()

        except Exception as error:
            description = f'Unable to create or send a ResourceState message: {str( error )}'
            LOGGER.error( description )
            await self.send_error_message(description)
            return False

        return True
    
    async def all_messages_received_for_epoch(self) -> bool:
        '''Component is ready to process a epoch if it uses a csv state source or if it has already gotten a ControlState message for the current epoch.'''
        return self._state_source is not None or (self._control_state_for_epoch is not None and self._control_state_for_epoch.epoch_number == self._latest_epoch)
    
    async def general_message_handler(self, message_object: Union[BaseMessage, Any],
                                      message_routing_key: str) -> None:
        '''Handle receiving of ControlState messages.'''
        # Check that we have a ControlState message and it is what we expect.
        if isinstance( message_object, ControlStatePowerSetpointMessage ):
            if message_object.epoch_number != self._latest_epoch:
                LOGGER.warning(f'Got a control state message with id {message_object.message_id} for epoch {message_object.epoch_number} but was expecting it for epoch {self._latest_epoch}.')
                # ignore message
                return
            
            if self._control_state_for_epoch is not None and self._control_state_for_epoch.epoch_number == message_object.epoch_number:
                LOGGER.warning(f'Already had received a control state message for epoch {self._latest_epoch} but received another one with message id {message_object.message_id}.')
                # ignore message
                return
            
            # got an expected message. Ready to process epoch.
            self._control_state_for_epoch = message_object
            self._triggering_message_ids.append(message_object.message_id)
            await self.start_epoch() 

    async def _send_resource_state_message(self):
        '''
        Calculates new state for the storage and publishes it as a ResourceState message.
        '''
        resource_state = self._get_resource_state_message()
        await self._rabbitmq_client.send_message(self._result_topic, resource_state.bytes())

    def _get_resource_state_message(self) -> ResourceStateMessage:
        '''
        Create a ResourceStateMessage from the new state of the storage.
        '''
        if self._state_source is not None:
            # get desired power from state source
            control_state = self._state_source.getNextEpochData()
            # add possible new customer id and node to storage so it can be included as a part of the resource state message
            self._storage.customer_id = control_state.customerid
            self._storage.node = control_state.node
            
        else:
            # get storage control information from received message
            control_state = ResourceState( customerid = None, real_power = self._control_state_for_epoch.real_power.value, reactive_power = self._control_state_for_epoch.reactive_power.value )
        
        # power desired from the storage
        real_power = control_state.real_power
        # calculate the duration of the epoch in hours required to calculate the new state of the storage
        epoch_start = to_utc_datetime_object( self._latest_epoch_message.start_time )
        epoch_end = to_utc_datetime_object( self._latest_epoch_message.end_time )
        epoch_duration = epoch_end -epoch_start
        epoch_duration_h = epoch_duration.total_seconds() /3600
        
        state = self._storage.calculate_state(real_power, epoch_duration_h)
        # create ResourceState message based on the storage state
        message = ResourceStateMessage(
            SimulationId = self.simulation_id,
            Type = ResourceStateMessage.CLASS_MESSAGE_TYPE,
            SourceProcessId = self.component_name,
            MessageId = next(self._message_id_generator),
            EpochNumber = self._latest_epoch,
            TriggeringMessageIds = self._triggering_message_ids,
            CustomerId = state.customerid,
            node = state.node,
            RealPower = state.real_power,
            ReactivePower = state.reactive_power,
            Node = state.node,
            StateOfCharge = state.state_of_charge 
            )
        
        if control_state.real_power != state.real_power:
            # storage could not operate with the required power so add a warning about it.
            message.warnings = [ 'warning.input.range' ]

        return message

def create_component() -> StorageResource:
    '''
    Create a StorageResource based on the initialization environment variables.
    '''
    # specify environment variables to be read.For optional ones mark default value as None though it is the default any way.
    env_variable_spec = (
        ( RESOURCE_STATE_CSV_FILE, str, None ),
        ( RESOURCE_STATE_CSV_DELIMITER, str, "," ),
        ( CUSTOMER_ID, str, None ),
        ( NODE, str, None ),
        ( CHARGE_RATE, float, 100.0 ),
        ( DISCHARGE_RATE, float, 100.0 ),
        ( CHARGE_EFFICIENCY, float, 90.0 ),
        ( DISCHARGE_EFFICIENCY, float, 90.0 ),
        ( KWH_RATED, float ),
        ( INITIAL_STATE_OF_CHARGE, float ),
        ( KW_RATED, float ),
        ( SELF_DISCHARGE, float, 0.0 )
    )
    
    environment = load_environmental_variables( *env_variable_spec )
    # check if some required environment variables were missing.
    missing = []
    for item in env_variable_spec:
        if len( item ) == 2:
            # no explicit default value given so this was required
            if environment[ item[0] ] is None:
                missing.append( item[0] )
    
    initialization_error = None             # possible initialization error message goes here
    if len( missing ) > 0:
        initialization_error = 'Component missing required initialization environment variables: '  +', '.join( missing )
    
    csv_file = environment[RESOURCE_STATE_CSV_FILE]
    
    state_source = None # if a state source is used it goes here.
    if csv_file is not None:
        node = None # no initial value for storage node. Read from csv.
        try:
            state_source = CsvFileResourceStateSource( csv_file, environment[RESOURCE_STATE_CSV_DELIMITER])
    
        except CsvFileError as error:
            initialization_error = f'Unable to create a csv file resource state source for the component: {str( error )}'
            
    elif csv_file is None:
        # Since currently ControlState message does not have node it can be set with environment variable
        node = environment[NODE]
        # since state source is not used customer id is required from environment
        # ResourceState message requires customer id and ControlState message does not include it.
        if environment[CUSTOMER_ID] is None:
            initialization_error = f'when {RESOURCE_STATE_CSV_FILE} initialization environment variable is not given {CUSTOMER_ID} is required.'

    storage = None
    try:
        # create storage state based on environment variables to be used by the component
        storage = StorageState(customer_id = environment[CUSTOMER_ID], node = node, initial_state_of_charge = environment[INITIAL_STATE_OF_CHARGE], kwh_rated = environment[KWH_RATED], kw_rated = environment[KW_RATED],
                            self_discharge = environment[SELF_DISCHARGE], charge_rate = environment[CHARGE_RATE],
                            discharge_rate = environment[DISCHARGE_RATE ], charge_efficiency = environment[CHARGE_EFFICIENCY],
                            discharge_efficiency = environment[DISCHARGE_EFFICIENCY])
        
    except Exception as err:
        initialization_error = f'Unable to create a storage state: {err}'
    # create component
    return StorageResource(storage,  state_source, initialization_error )

async def start_component():
    '''
    Create and start a StorageResource component.
    '''
    try:
        resource = create_component()
        await resource.start()
        while not resource.is_stopped:
            await asyncio.sleep( 2 )
    except Exception as error:
        LOGGER.error("{} : {}".format(type(error).__name__, error))

if __name__ == '__main__':
    asyncio.run(start_component())
