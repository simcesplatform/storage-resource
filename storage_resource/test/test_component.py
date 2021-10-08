# -*- coding: utf-8 -*-
# Copyright 2021 Tampere University and VTT Technical Research Centre of Finland
# This software was developed as a part of the ProCemPlus project: https://www.senecc.fi/projects/procemplus
# This source code is licensed under the MIT license. See LICENSE in the repository root directory.
# Author(s): Otto Hylli <otto.hylli@tuni.fi>
#            Antti Keski-Koukkari <antti.keski-koukkari@vtt.fi>

'''
Tests for the StorageResource  component.
'''

from typing import List, Tuple, Union, cast
import os 
import pathlib
import csv

from tools.messages import AbstractMessage
from domain_messages.resource import ResourceStateMessage 

from tools.tests.components import MessageGenerator, TestAbstractSimulationComponent

from storage_resource.component import create_component, RESOURCE_STATE_CSV_FILE, INITIAL_STATE_OF_CHARGE, KWH_RATED, DISCHARGE_EFFICIENCY, CHARGE_EFFICIENCY, KW_RATED, SELF_DISCHARGE       
from domain_tools.resource.resource_state_source import ResourceState 

class ManagerMessageGenerator( MessageGenerator ):
    '''
    Custom generator for simulation manager messages. Has a 15 minute epoch.
    '''
    
    def __init__(self, simulation_id: str, process_id: str):
        '''
        Create a message generator with 15 minute epoch length.
        '''
        super().__init__( simulation_id, process_id )
        self.epoch_interval = 900

class ResourceStateMessageGenerator( MessageGenerator ):
    """Message generator for the tests. extended to produce the expected ResourceState messages."""
    
    def __init__(self, simulation_id: str, process_id: str):
        super().__init__( simulation_id, process_id)
        # read expected resource states from csv.
        with open( pathlib.Path( __file__ ).parent.absolute() / 'test1.csv', newline = '', encoding = 'utf-8') as file:
            data = csv.DictReader( file, delimiter = ',' )
            # for each epoch a tuple consisting of expected state and is a warning expected on that epoch.
            # epoch 0 has no state
            self.states = [ (None, False) ]
            for row in data:
                node = row['node']
                node = int(node) if node != '' else None
                # warning column in csv has an x if a warning is expected.
                self.states.append( (ResourceState( real_power = float(row['resource_state_power']), reactive_power = 0.0, customerid = 'customer1', state_of_charge = float(row['state_of_charge']), node = node), True if row['warning'] == 'x' else False ))

    def get_resource_state_message(self, epoch_number: int, triggering_message_ids: List[str]) -> Union[ResourceStateMessage, None]:
        """Get the expected ResourceStateMessage for the given epoch."""
        if epoch_number == 0 or epoch_number >= len( self.states ):
            return None
        
        # get the resource state for this epoch and is a warning expected.
        state, produces_warning  = self.states[ epoch_number ]
        self.latest_message_id = next(self.id_generator)
        resource_state_message = ResourceStateMessage(**{
            "Type": "ResourceState",
            "SimulationId": self.simulation_id,
            "SourceProcessId": self.process_id,
            "MessageId": self.latest_message_id,
            "EpochNumber": epoch_number,
            "TriggeringMessageIds": triggering_message_ids,
            "RealPower": state.real_power,
            "ReactivePower": state.reactive_power,
            "StateOfCharge": state.state_of_charge,
            "CustomerId": state.customerid,
            "Node": state.node
        })
        
        if produces_warning:
            resource_state_message.warnings = [ 'warning.input.range' ]
            
        return resource_state_message

class TestStorageResourceComponent( TestAbstractSimulationComponent ):
    """Unit tests for StorageResource.""" 
    
    # the method which initializes the component
    component_creator = create_component
    message_generator_type = ResourceStateMessageGenerator
    normal_simulation_epochs = 24
    # use custom manager whose epoch length matches the test data.
    manager_message_generator = ManagerMessageGenerator( TestAbstractSimulationComponent.simulation_id, TestAbstractSimulationComponent.test_manager_name )
    
    # specify component initialization environment variables.
    os.environ[ RESOURCE_STATE_CSV_FILE ] = str( pathlib.Path(__file__).parent.absolute() / 'test1_state.csv' )
    os.environ[ INITIAL_STATE_OF_CHARGE ] = str( 50 )
    os.environ[KWH_RATED] = str(100)
    os.environ[CHARGE_EFFICIENCY] = str(90)
    os.environ[DISCHARGE_EFFICIENCY] = str(90)
    os.environ[KW_RATED] = str(100)
    os.environ[SELF_DISCHARGE] = str(0.2)
    
    def get_expected_messages(self, component_message_generator: ResourceStateMessageGenerator, epoch_number: int, triggering_message_ids: List[str]) -> List[Tuple[AbstractMessage, str]]:
        """Get the messages and topics the component is expected to publish in given epoch."""
        if epoch_number == 0:
            return [
                (component_message_generator.get_status_message(epoch_number, triggering_message_ids), "Status.Ready")
                ]
            
        return [
            (component_message_generator.get_resource_state_message(epoch_number, triggering_message_ids), "ResourceState.Storage." +self.component_name ),
            (component_message_generator.get_status_message(epoch_number, triggering_message_ids), "Status.Ready")
        ]
        
    def compare_resource_state_message(self, first_message: ResourceStateMessage, second_message: ResourceStateMessage ):
        """Check that the two ResourceState messages have the same content."""
        self.compare_abstract_result_message(first_message, second_message)
        # use almost equal since conversion between binary and decimal may cause some minor differences.
        self.assertAlmostEqual( first_message.real_power.value, second_message.real_power.value )
        self.assertEqual( first_message.real_power.unit_of_measure, second_message.real_power.unit_of_measure )
        self.assertAlmostEqual( first_message.reactive_power.value, second_message.reactive_power.value )
        self.assertEqual( first_message.reactive_power.unit_of_measure, second_message.reactive_power.unit_of_measure )
        self.assertAlmostEqual( first_message.state_of_charge.value, second_message.state_of_charge.value )
        self.assertEqual( first_message.state_of_charge.unit_of_measure, second_message.state_of_charge.unit_of_measure )
        self.assertEqual( first_message.customerid, second_message.customerid )
        self.assertEqual( first_message.node, second_message.node )
        self.assertEqual( first_message.warnings, second_message.warnings )
        
    def compare_message(self, first_message: AbstractMessage, second_message: AbstractMessage) -> bool:
        """Override the super class implementation to add the comparison of ResourceState messages.""" 
        if super().compare_message(first_message, second_message):
            return True

        if isinstance(second_message, ResourceStateMessage ):
            self.compare_resource_state_message(cast(ResourceStateMessage, first_message), second_message)
            return True

        return False
