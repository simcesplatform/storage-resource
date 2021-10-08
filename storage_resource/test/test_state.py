# -*- coding: utf-8 -*-
# Copyright 2021 Tampere University and VTT Technical Research Centre of Finland
# This software was developed as a part of the ProCemPlus project: https://www.senecc.fi/projects/procemplus
# This source code is licensed under the MIT license. See LICENSE in the repository root directory.
# Author(s): Otto Hylli <otto.hylli@tuni.fi>
#            Antti Keski-Koukkari <antti.keski-koukkari@vtt.fi>

'''
Tests for the storage state.
'''
import pathlib
from csv import DictReader
import unittest

from storage_resource.state import StorageState

class TeststorageState(unittest.TestCase):
    '''Tests for the storage state.'''

    def test_check_percentage(self):
        '''Test that the StoragesTate internal _check_percentage method works.'''
        # test values and should they be accepted or should they raise an exception
        tests = [
            ( 10, True ),
            ( 100.0, True ),
            ( '0.0', True ),
            ( -1.0, False ),
            ( 100.1, False ),
            ( None, False )
        ]
        
        for value, is_ok in tests:
            if is_ok:
                self.assertEqual( StorageState._check_percentage( value, 'test' ), float(value) )
                
            else:
                with self.assertRaises( ValueError ):
                    StorageState._check_percentage( value, 'test' )
                    
    def test_check_positive_float(self):
        '''Test that the StoragesTate internal _check_positive_float method works.'''
        # test values and should they be accepted or should they raise an exception
        tests = [
            ( 10, True ),
            ( 100.0, True ),
            ( '0.0', True ),
            ( -1.0, False ),
            ( 100.1, True ),
            ( None, False ),
            ( 'foo', False )
        ]
        
        for value, is_ok in tests:
            if is_ok:
                self.assertEqual( StorageState._check_positive_float( value, 'test' ), float(value) )
                
            else:
                with self.assertRaises( ValueError ):
                    StorageState._check_positive_float( value, 'test' )
                    
    def test_create_storage_state(self):
        '''Test that creation of StorageState succeeds with valid parameters and fails with invalid ones.'''
        # test creation parameters and if they should work or not
        tests = [
            ({
                'customer_id': 'customerid',
                'node': 1,
                'charge_rate': 99.0,
                'discharge_rate': 95.0,
                'charge_efficiency': 91.0,
                'discharge_efficiency': 85.0,
                'kwh_rated': 110.0,
                'initial_state_of_charge': 50.0,
                'kw_rated': 80.0,
                'self_discharge': 0.5
            }, True ),
            # without parameters who have a default value.
            ({
                'customer_id': 'customerid',
                'kwh_rated': 110.0,
                'initial_state_of_charge': 50.0,
                'kw_rated': 80.0
            }, True ),
            # invalid value for node
            ({
                'customer_id': 'customerid',
                'node': 'foo',
                'kwh_rated': 110.0,
                'initial_state_of_charge': 50.0,
                'kw_rated': 80.0
            }, False ),
            # initial_state_of_charge is larger than 100
            ({
                'customer_id': 'customerid',
                'charge_rate': 99.0,
                'discharge_rate': 95.0,
                'charge_efficiency': 91.0,
                'discharge_efficiency': 85.0,
                'kwh_rated': 110.0,
                'initial_state_of_charge': 150.0,
                'kw_rated': 80.0,
                'self_discharge': 0.5
            }, False ),
            # charge rate is negative
            ({
                'customer_id': 'customerid',
                'charge_rate': -99.0,
                'discharge_rate': 95.0,
                'charge_efficiency': 91.0,
                'discharge_efficiency': 85.0,
                'kwh_rated': 110.0,
                'initial_state_of_charge': 50.0,
                'kw_rated': 80.0,
                'self_discharge': 0.5
            }, False ),
            # kwh_rated cannot be converted to float
            ({
                'customer_id': 'customerid',
                'charge_rate': 99.0,
                'discharge_rate': 95.0,
                'charge_efficiency': 91.0,
                'discharge_efficiency': 85.0,
                'kwh_rated': 'foo',
                'initial_state_of_charge': 50.0,
                'kw_rated': 80.0,
                'self_discharge': 0.5
            }, False )
        ]
        
        for init_params, is_ok in tests:
            with self.subTest( params = init_params, is_ok = is_ok ):
                if is_ok:
                    storage = StorageState(**init_params)
                    self.assertEqual( storage.customer_id, init_params.get('customer_id'))
                    self.assertEqual( storage.charge_rate, init_params.get('charge_rate', 100.0))
                    self.assertEqual( storage.discharge_rate, init_params.get('discharge_rate', 100.0))
                    self.assertEqual( storage.charge_efficiency, init_params.get('charge_efficiency', 90.0))
                    self.assertEqual( storage.discharge_efficiency, init_params.get('discharge_efficiency', 90.0))
                    self.assertEqual( storage.kwh_rated, init_params.get('kwh_rated'))
                    self.assertEqual( storage.initial_state_of_charge, init_params.get('initial_state_of_charge'))
                    self.assertEqual( storage.kw_rated, init_params.get('kw_rated'))
                    self.assertEqual( storage.self_discharge, init_params.get('self_discharge', 0.0))
                    
                else:
                    with self.assertRaises( ValueError ):
                        StorageState( **init_params )
                        
    def test_calculate_storage_state(self):
        '''Test that storage state is calculated correctly.'''
        # tests containing constructor parameters and csv file containing power values and expected power and charge state values. 
        tests = [
            {
                'file': 'test1.csv',
                'duration_h': 0.25,
                'customer_id': 'customer1',
                'initial_state_of_charge': 50,
                'kwh_rated': 100,
                'discharge_efficiency': 90,
                'charge_efficiency': 90,
                'kw_rated': 100,
                'self_discharge': 0.2
            }
        ]
        
        for test_params in tests:
            with self.subTest( file = test_params['file']):
                file = pathlib.Path(__file__).parent.absolute() / test_params['file']
                with open( file, newline = '', encoding = 'utf-8') as file:
                    del test_params['file']
                    self._test_calculate_state_with_params( file, test_params )
                
    def _test_calculate_state_with_params(self, file, params: dict ):
        '''The actual check for each test defined in test_calculate_storage_state.'''
        csv_data = DictReader( file, delimiter = ',')
        duration_h = params['duration_h']
        del params['duration_h']
        storage = StorageState( **params )
        # calculate state for each control state real power and check that resource state real power and state of charge match expected
        for row in csv_data:
            node = row.get('node', '')
            node = int(node) if node != '' else None
            storage.node = node
            state = storage.calculate_state( float(row['control_state_power']), duration_h)
            # error message for asserts
            message = f'Unexpected state in epoch {row["epoch"]}'
            self.assertEqual( state.customerid, row.get('CustomerId', params['customer_id']), message )
            self.assertEqual( state.node, node, message )
            # use almost equal since there might be small differences when converting decimal numbers from the csv to binary
            self.assertAlmostEqual( state.real_power, float(row['resource_state_power']), msg = message )
            self.assertAlmostEqual( state.reactive_power, float(row.get('resource_state_reactive_power', 0.0)), msg = message )
            self.assertAlmostEqual( state.state_of_charge, float(row['state_of_charge']), msg = message )
            
if __name__ == "__main__":
    unittest.main()