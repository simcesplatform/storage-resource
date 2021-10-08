# Storage resource

A component for simulating a resource which stores energy. The storage is given a initial state and is then controlled in each epoch by asking for desired power input or output. This control information can be read from a csv file or received in each epoch from ControlState messages. The storage reports its state in each epoch with a ResourceState message containing the power input or output and the state of charge as a percentage. If the storage cannot fullfil the desired power for example there is not enough energy stored, the actual power the storage is capable of is reported and the message contains a warning.input.range warning.

## Requirements

- python 3.7
- pip for installing requirements

Install requirements:

```bash
# optional create a virtual environment:
python3 -m venv .env
# activate it
. .env/bin/activate # *nix
.env\scripts\activate # windows.
# install required packages
pip install -r requirements.txt
```

## Usage

The component is based on the AbstractSimulationCompoment class from the [simulation-tools](https://github.com/simcesplatform/simulation-tools)
 repository. It is configured via environment variables which include common variables for all AbstractSimulationComponent subclasses such as rabbitmq connection and component name. Environment variables specific to this component are listed below:

- RESOURCE_STATE_CSV_FILE (optional): Location of the csv file which contains the control information used in the simulation for each epoch. Relative file paths are in relation to the current working directory. If this is not given the component expects control information from ControlState messages.
- RESOURCE_STATE_CSV_DELIMITER (optional, default ,): Delimiter used in the csv file.
- RESOURCE_STATE_TOPIC (optional, default ResourceState): The upper level topic under whose subtopics the ResourceState messages are published.
- CONTROL_STATE_TOPIC (optional, default ControlState) If RESOURCE_STATE_CSV_FILE is not given expects to get ControlState messages from its own subtopic under the given main control state topic. E.g. if component id is my-storage and default topic is used listens to ControlState.my-storage.
- CUSTOMER_ID (optional): Name of customer id to which the resource is associated with. Required if RESOURCE_STATE_CSV_FILE is not given. 
- NODE (optional): Node that 1-phase resource is connected to. Possible values 1, 2 and 3. Used if csv file state source is not used.
- CHARGE_RATE (optional, default 100.0): Charging rate (input power) in Percent of rated kW.
- DISCHARGE_RATE (optional, default  100.0): Discharge rate (output power) in Percent of rated kW.  
- INITIAL_STATE_OF_CHARGE (required): Initial amount of energy stored, %.
- KWH_RATED (required): Rated storage capacity in kWh.
- DISCHARGE_EFFICIENCY (optional, default 90.0): Percent, efficiency for discharging the storage.
- CHARGE_EFFICIENCY (optional, default 90.0): Percent, efficiency for charging the storage.
- KW_RATED (required): kW rating of power output. 
- SELF_DISCHARGE (optional, default 0.0): Percent of rated kWh drained from storage while idling.

When using a CSV file as control state source the file should contain the following columns: RealPower, ReactivePower and CustomerId. A optional Node column can be used. The file may include other columns which will be just ignored by the component. ReactivePower is currently not used so it can be for example always zero. Each row containing values will then represent data for one epoch. There should be at least as many data rows as there will be epochs. Decimal separator is "." and column separator is by default "," which can be changed with the RESOURCE_STATE_CSV_DELIMITER environment variable.

The component can be started with:

    python -m storage_resource.component

It can be also used with docker via the included dockerfile.

## Tests 

The included unittests can be executed with:

    python -m unittest

This requires RabbitMQ connection information provided via environment variables as required by the AbstractSimulationComponent class. Tests can also be executed with docker compose:

    docker-compose -f docker-compose-test.yml up --build
    
After executing tests exit with ctrl-c and remove the test environment:

    docker-compose -f docker-compose-test.yml down -v

### Test files

Some of the tests utilize csv files namely a test for the component using csv state source and a test for the storage state. Both use the test1.csv which includes the following columns:

- epoch: number of epoch test data is for
- control_state_power: Power requested from the storage.
- resource_state_power: Expected actual power the storage could operate at.
- state_of_charge: Expected charge percentage of the storage after the epoch.
- node: Expected node. Empty if no value.
- warning: Used in the component test to indicate if the ResourceState message should contain a warning.input.range warning. Empty if warning is not expected x if warning is expected.

The component test also uses the test1_state.csv file as the resource state csv file.