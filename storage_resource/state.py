# -*- coding: utf-8 -*-
# Copyright 2021 Tampere University and VTT Technical Research Centre of Finland
# This software was developed as a part of the ProCemPlus project: https://www.senecc.fi/projects/procemplus
# This source code is licensed under the MIT license. See LICENSE in the repository root directory.
# Author(s): Otto Hylli <otto.hylli@tuni.fi>
#            Antti Keski-Koukkari <antti.keski-koukkari@vtt.fi>

'''
Contains a class for representing and calculating the internal state of a storage resource  
'''

from typing import Union, Any, Callable

from domain_tools.resource.resource_state_source import ResourceState
from tools.tools import FullLogger

LOGGER = FullLogger(__name__)

class StorageState(object):
    '''
    a class for representing and calculating the internal state of a storage resource
    '''

    def __init__(self, customer_id: str,  kwh_rated: float, initial_state_of_charge: float, kw_rated: float, self_discharge: float = 0.0,
                 charge_rate: float = 100.0, discharge_rate: float = 100.0, charge_efficiency: float = 90.0, 
                 discharge_efficiency: float = 90, node: Union[float, None] = None ):
        '''
        Create a storage state with given properties and initial state.
        Raises ValueError if property value is invalid. See each property's description for validity requirements.
        '''
        self.customer_id = customer_id
        self.node = node
        self.charge_rate = charge_rate
        self.discharge_rate = discharge_rate
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency
        self.kwh_rated = kwh_rated
        self.initial_state_of_charge = initial_state_of_charge
        self.kw_rated = kw_rated
        self.self_discharge = self_discharge
    
    @property
    def customer_id(self) -> Union[str, None]:
        '''Name of customer id to which the resource is associated with.'''
        return self._customer_id
    
    @customer_id.setter
    def customer_id(self, customer_id: Union[str, None] ):
        '''Set value for customer_id.'''
        if customer_id is None:
            self._customer_id = None
            
        else:
            self._customer_id = str(customer_id)

    @property
    def node(self) -> Union[int, None]:
        '''Node that 1-phase resource is connected to.
        If this is None then it is assumed that the resource is 3-phase resource.'''
        return self._node

    @node.setter
    def node(self, node: Union[int, None]):
        '''Set value for node. Allowed values are 1, 2, 3 and None.'''
        if node is None:
            self._node = None
            return

        try:
            node = int(node)
            if node not in [1, 2,  3]:
                raise ValueError()

            self._node = node

        except ValueError:
            raise ValueError(f'{node} is an invalid value for node. Allowed values are 1, 2, 3 or None')

    @property
    def charge_rate(self) -> float:
        '''Charging rate (input power) in Percent of rated kW.'''
        return self._charge_rate
    
    @charge_rate.setter
    def charge_rate(self, charge_rate: float):
        '''Set charge rate value. Must be between 0 and 100 otherwise ValuError is raised..'''
        self._charge_rate = self._check_percentage( charge_rate, 'charge rate'  )
        
    @property
    def discharge_rate(self) -> float:
        '''Discharge rate (output power) in Percent of rated kW.'''
        return self._discharge_rate
    
    @discharge_rate.setter
    def discharge_rate(self, discharge_rate: float):
        '''Set discharge rate value. Must be between 0 and 100 otherwise ValuError is raised..'''
        self._discharge_rate = self._check_percentage( discharge_rate, 'discharge rate'  )
    
    @property
    def charge_efficiency(self) -> float:
        '''Percent, efficiency for charging the storage.'''
        return self._charge_efficiency
    
    @charge_efficiency.setter
    def charge_efficiency(self, charge_efficiency: float):
        '''Set charge efficiency rate value. Must be between 0 and 100 otherwise ValuError is raised..'''
        self._charge_efficiency = self._check_percentage( charge_efficiency, 'charge efficiency'  )
    
    @property
    def discharge_efficiency(self) -> float:
        '''Percent, efficiency for discharging the storage.'''
        return self._discharge_efficiency
    
    @discharge_efficiency.setter
    def discharge_efficiency(self, discharge_efficiency: float):
        '''Set discharge efficiency rate value. Must be between 0 and 100 otherwise ValuError is raised..'''
        self._discharge_efficiency = self._check_percentage( discharge_efficiency, 'discharge efficiency'  )
        
    @property
    def kwh_rated(self) -> float:
        '''Rated storage capacity in kWh.'''
        return self._kwh_rated
    
    @kwh_rated.setter
    def kwh_rated(self, kwh_rated: float):
        '''Set kwh_rated value.'''
        self._kwh_rated = self._check_positive_float(kwh_rated, 'kwh_rated')
    
    @property
    def initial_state_of_charge(self) -> float:
        '''Initial amount of energy stored, %. '''
        return self._initial_state_of_charge
    
    @initial_state_of_charge.setter
    def initial_state_of_charge(self, initial_state_of_charge: float):
        '''Set initial_state_of_charge value. Also sets kwh_stored_current value.
        Must be between 0 and 100 otherwise ValueError is raised..'''
        initial_state_of_charge = self._check_percentage(initial_state_of_charge, 'initial state of charge')
        
        self._initial_state_of_charge = initial_state_of_charge
        self.kwh_stored_current = self.kwh_rated*(initial_state_of_charge/100)
        
    @property
    def kwh_stored_current(self) -> float:
        '''Current amount of energy stored, kWh. '''
        return self._kwh_stored_current
    
    @kwh_stored_current.setter
    def kwh_stored_current(self, kwh_stored_current: float):
        '''Set kwh_stored_current value.'''
        self._kwh_stored_current = self._check_positive_float(kwh_stored_current, 'kwh stored current')
        
    @property
    def kw_rated(self) -> float:
        '''kW rating of power output.'''
        return self._kw_rated
    
    @kw_rated.setter
    def kw_rated(self, kw_rated: float):
        '''Set kw_rated value.'''
        self._kw_rated = self._check_positive_float(kw_rated, 'kw_rated')
        
    @property
    def self_discharge(self) -> float:
        '''Percent of rated kWh drained from storage while idling.'''
        return self._self_discharge
    
    @self_discharge.setter
    def self_discharge(self, self_discharge: float):
        '''Set self_discharge value. Must be between 0 and 100 otherwise ValueError is raised..'''
        self._self_discharge = self._check_percentage( self_discharge, 'self discharge')
    
    @property
    def state_of_charge(self) -> float:
        '''Present amount of energy stored, % of rated kWh.'''
        return self.kwh_stored_current /self.kwh_rated *100.0
    
    @property
    def max_discharge_power(self) -> float:
        '''Maximum power for discharging the storage.'''
        return self.discharge_rate /100 *self.kw_rated
    
    @property
    def max_charge_power(self) -> float:
        '''Maximum power for charging the storage.'''
        return -(self.charge_rate /100 *self.kw_rated)
    
    def calculate_state(self, real_power: float, duration_h: float ) -> ResourceState:
        '''Calculate the new state of the storage after the given amount of time has passed and the storage has been requested to operate with the given power during it.
         real_power: Power desired from the storage. Negative means that storage is charged and positive that it is discharged.
         duration_h: The amount of time in hours the storage should be operating with the desired power. Raises value error if value is not positive.
         Returns ResourceState describing the storage's state after the operation notably its state of charge and real 
         power which may differ from the requested power if for example the storage did not have enough energy stored 
         for producing the desired power output.'''
        if duration_h < 0.0:
            raise ValueError(f'{duration_h} is an invalid value for duration_h. It should be positive.')
        
        LOGGER.debug(f'{real_power} kW requested from storage for {duration_h} hours.')
        # check that storage has not been requested to operate over its maximum charge or discharge rate
        # if it has the maximum possible power will be used instead of the requested one.    
        if real_power > self.max_discharge_power:
            real_power = self.max_discharge_power
            LOGGER.debug(f'Requested to operate over maximum discharge rate. Using maximum discharge power {real_power} instead.')
            
        elif real_power < self.max_charge_power:
            real_power = self.max_charge_power
            LOGGER.debug(f'Requested to operate over maximum charge rate. Using maximum charge power {real_power} instead.')
        
        # calculate the new amount of energy the storage would have if it operated with the real power
        # taking in to account the efficiency of charging or discharging     
        if real_power >= 0:
            # storage will be discharged so discharge efficiency will be used to scale the actual energy
            # this will be negative so that the energy will be subtracted from the current stored energy
            efficiency_factor = -1 /(self.discharge_efficiency /100) 
            
        else:
            # storage is charged use charge efficiency
            # this has to be negative so that energy from negative power turns positive and will be added to current energy
            efficiency_factor = -self.charge_efficiency /100
        
        # calculate the energy always consumed by the storage 
        idle_energy = self.self_discharge/100*self.kwh_rated*duration_h
        # calculate new amount of energy with the requested power and the idle energy
        kwh_stored_next = self.kwh_stored_current  +efficiency_factor *real_power *duration_h -idle_energy
        #LOGGER.debug(f'Currently storing {self.kwh_stored_current} kWh energy. After requested operation would store {kwh_current_next} kWh.')
        
        # check if storage actually can produce / consume the desired energy
        max_energy = None # maximum energy the storage can store or output in its current state
        if kwh_stored_next < 0:
            LOGGER.debug(f'Storage does not have enough energy.')
            # storage cannot produce the required amount of energy
            # calculate the maximum amount it can produce which takes in to account the idle energy
            # this will be negative so that power calculation later produces a positive power
            max_energy = -(self.kwh_stored_current -idle_energy)
            if max_energy > 0:
                # there is no energy available at all  
                max_energy = 0.0
                
            kwh_stored_next = 0.0 # storage will be empty
            
        elif kwh_stored_next > self.kwh_rated:
            LOGGER.debug(f'Storage cannot store all of the energy.')
            # storage cannot store all of the energy
            # calculate the amount of energy it can store
            max_energy = self.kwh_rated -self.kwh_stored_current +idle_energy
            # storage will be full
            kwh_stored_next = self.kwh_rated
        
        if max_energy is not None and real_power != 0.0:
            # storage has been requested to produce / consume too much energy
            # from the energy it can produce / consume calculate the real power    
            real_power = max_energy /duration_h /efficiency_factor
        
        LOGGER.debug(f'Stored {self.kwh_stored_current} kWh, Operated at {real_power} kW for {duration_h} h. Now storing {kwh_stored_next} kWh.')
        # set current amount of energy and return resource state information 
        self.kwh_stored_current = kwh_stored_next
        
        return ResourceState( customerid = self.customer_id, node = self.node, real_power = real_power, reactive_power = 0.0, state_of_charge = self.state_of_charge )
    
    @classmethod
    def _check_percentage(cls, value: Any, name: str ) -> float:
        '''Check that given value can be converted to float and that it is between 0 and 100. If successful the value as float will be returned.
        If the check fails ValueError will be raised.
        Name will be used in error messages to indicate for what attribute the value was meant for.'''
        return cls._check_float( value, name, lambda x : x >= 0.0 and x <= 100.0, 'between 0.0 and 100.0')
    
    @classmethod
    def _check_positive_float(cls, value: Any, name: str ) -> float:
        '''Check that given value can be converted to float and that it is positive. Value as float will be returned if check is successful.
        If the check fails ValueError will be raised.
        Name will be used in error messages to indicate for what attribute the value was meant for.'''
        return cls._check_float( value, name, lambda x : x >= 0.0, 'positive')
        
    @classmethod    
    def _check_float(cls, value: Any, name: str, value_check: Callable[[float], bool], should_be_msg: str ) -> float:
        '''Check that given value can be converted to float and that value satisfies the extra check. Value as float will be returned if check is successful.
        If the conversion or check fails ValueError will be raised.
        Name will be used in error messages to indicate for what attribute the value was meant for.
        should_be_msg is used to indicate in error message what kind of values the extra check expects.
        value_check is a callable which expects a float value and returns True if the value passes the check.'''
        if value is None:
            raise ValueError(f'{name} cannot be None.')
        
        try:
            value = float(value)
        
        except ValueError:
            raise ValueError(f'{value} cannot be converted to float for {name}.')
        
        if not value_check( value ):
            raise ValueError(f'{value} is an invalid value for {name} it should be {should_be_msg}.')
        
        return value