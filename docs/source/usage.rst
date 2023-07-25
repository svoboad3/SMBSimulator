Usage
=====

.. _Requirements:

Requirements
------------

This application was created and tested using these components

* Industrial Edge App Publisher V1.9.5
* Docker Engine 20.10.21
* Docker Compose V2.4
* Industrial Edge Virtual Device V1.12.0-3-a
* IE Databus Configurator V2.0.0-5
* IE Databus V2.0.0-4
* IE Common Connector Configurator V1.8.2-3
* IE SIMATIC S7 Connector V1.8.1-7
* IE Data Service V1.5.0
* IE Management System V1.1.0-48

Further requirements:

* IE Device is onboarded to a IE Management
* IE Databus Configurator is deployed to the IE Management
* IE Databus is deployed to the IE Device

.. _Installation:

Installation
------------

1. Pull Git project from this `repository`_.
2. Create docker image.
.. code-block::
    docker build -t "ie-smb-sim" ..
3. Create application using IE App Publisher and docker-compose.yml file.
4. Upload it to IE Management.
5. Install it to IE Device.

Please refer to `Uploading App to IEM`_ on how to upload the app to the IEM.

.. _repository: https://github.com/svoboad3/SMBSimulator
.. _Uploading App to IEM: https://github.com/industrial-edge/upload-app-to-industrial-edge-management

.. _Configuring the Industrial Edge Databus:

Configuring the Industrial Edge Databus
---------------------------------------

IE SMB-sim application requires Industrial Edge Databus application to be installed and configured.

* In the Industrial Edge Management Web interface, click on "Data Connections" and select the Databus
* Select the corresponding Industrial Edge Device and click "Launch"
* Create a new user with the username and password defined as "edge" and "edge"
* Create the topic "ie/#" and give the user publish and subscribe permission
* Deploy the databus configuration and wait for the job to be finished successfully

.. _Configuring the SIMATIC S7 Connector:

Configuring the SIMATIC S7 Connector
------------------------------------

IE SMB-sim application requires SIMATIC S7 Connector application to be installed and configured.

* In the Industrial Edge Management Web interface, click on "Data Connections" and select the Databus
* Select the corresponding Industrial Edge Device and click "Launch"
* Import configuration file IEVD2.json
* Deploy the tags to Industrial Edge Device
* Start Project

.. _Configuring the Data Service:

Configuring the Data Service
----------------------------

IE SMB-sim application requires Data Service application to be installed and configured.

* In the Industrial Edge Device Web interface, click on "Apps" and select the Data Service
* Select "Connectors" and activate predefined SIMATIC S7 Connector
* In "Assets & Connectivity" select Add multiple variables and select all variables from SIMATIC S7 Connector and click "Save"

.. _User Manual:

User Manual
-----------

* Application page can be accessed through IED in Apps tab.
* First, login is required with same credentials as login to IED.
* Then choose between offline and online simulation. Offline being just the simulation until specified time. Online running alongside real SMB process.
* Next define SMB station by creating columns in specific zones. After there is at least one column in each zone, you can continue.
* Next define separation mixture by adding components.
* Next step in offline simulation is to define flow rates and model calculation parameters.
* Next step in online simulation is to map tags to simulation parameters and define time and diferences.
* After that you can launch simulation.