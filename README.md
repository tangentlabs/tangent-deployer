Tangent Deployer
================

Fabric script for deploying projects to AWS.

Installation and Usage
----------------------

Installing and using the tangent deployer is easy. Install the package:

    pip install tangent-deployer

Create the following files:

    * deploy/fabconfig.py
    * deploy/fabfile.py

from the [fabric templates](templates) below and fill in the config with your 
project specific settings.

You'll also need to create a ``deploy/bootstrap`` directory and add the 
files from the deployers [bootstrap directory](bootstrap).

Once you've added these files you'll need to add your docker registry auth
token and then you'll be able to deploy with:

    fab <environment> deploy
