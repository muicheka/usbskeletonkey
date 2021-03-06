![Skeleton Key Logo][LOGO]

USB Skeleton Key
=================
Skeleton Key is a physical pen-testing framework that makes use of a Raspberry Pi micro-controller to provide a portable and streamline Enumeration/Exploitation capabilities

Features
---------
  * Enumerate		- Enumerate a range of hosts, print results to a bootstrap-based HTML page.
  * Responder		- Capture hashes and fingerprint a host with SpiderLabs Responder, over USB. 
  * Storage		- Emulate a storage device of any supported size or format.
  * KeyInject		- Utilize keystroke injection with either DuckyScript or SkeleScript.
  * Expandable		..or add your own

Setup
-------------
When making use of the Pi we have used a Raspberry Pi Zero equipped with a LED PHAT in order to provide status lights (Although this is optional). The HAT we make use of by default is the [Blinkt kit][BLINKT] and we also make use of a [USB Stem kit][USBSTEM] to provide that USB stick look and feel.

Some of the default modules require python 3.6, using a older version of python may produce unexpected results for which we offer no support.

Install USB Skeleton Key by running:
```commandline
git clone https://github.com/AR-Calder/usbskeletonkey.git
./install.sh
sudo python3.6 skeleton-key.py
```

In order to use Skeleton-Key to its fullest potential it is recommended that you run it on boot, but keep track of the session.

This can be done with tmux in the following way:

	## inside rc.local file	
	#!/bin/sh -e
	
	# always good and safe to use the complete path
	/usr/bin/tmux new-session -d -s skeletonKey

	# This statement is a life-saver, if ever your code crashes
	/usr/bin/tmux set-option -t skeletonKey set-remain-on-exit on

	# Create a window where you wish to run a code
	/usr/bin/tmux new-window -d -n 'Skeleton Key' -t skeletonKey:1 'cd /home/pi/usbskeletonkey; sudo python3 skeleton-key.py '
	
 	exit 0
	
After first run you must manually switch from config mode to armed mode, this can be done in the config.ini which will be generated in the base directory after first run. We also recommend 

Contribute
-----------
- [Issue Tracker][ISSUES]
- [Source Code][PROJECT]

Support
--------
If you are having any issues, please create an issue with a detailed explanation of the encountered problem.
Try to reproduce the issue with debug mode enabled as it provides clues as to where an issue may have occurred. 

License
--------
The project is licensed under the

See the [Legal Disclaimer][LEGAL] for information on this projects legal bounds


skeleton-key.py
================
With config set to true, this part of the project acts as the UI and allows the user to configure module setting before deployment on a target system.

Install Project

1. run skeleton-key.py
    2. select module
    3. configure module
4. saved ready for deployment

With config set to false it acts as the "Armed Mode" controller which loads all the configuration data and runs modules accordingly.

Interface Features
---------
- View all installed modules
- Configure any installed module
- Set the load order for enabled modules


Interface use
--------------
Modules are selected by a index number in the following form:

    --------------------
    1   Enumerate
    2   Ducky Script
    3   Responder
    4   SomeOtherModule
    --------------------

Once a module is selected, configuration mode for said module is entered.
The following commands can be used to interact with configuration mode:

    command				- Description of command
    --------------------------------------------------------------------------------------------------
    show				        - shows all info on the current module
    show [attribute]		    - shows the info on the specified attribute of the current module e.g. options
    set				            - displays instructions on how to use the set command
    set [attribute]			    - allows the user to enter a value to set the specified attribute for the current module
    set [attribute] [value]	    - sets the value for the specified attribute for the current module
    order                       - displays instructions on how to use the order command
    order [index] [index]       - move module at from current index to target index
    order [index] [direction]   - move module by one position \<up/down\>
    exit 				        - exits configuration mode


Examples
----------
show Enumerate			- Shows all information on the module Enumerate

show Enumerate options		- Shows all information on the options of Enumerate

set port_targets  		- Enters input mode to enter a value for port_targets of current module

set port_targets 55-1000	- Sets port_targets to the range 55-1000 on the current module

Interface Bugs
-----
Interface is not perfect therefore, will at times, throw errors.
Many of these errors have been fixed or altered but some may still creep in.
For this, we ask that you report any bugs or even write a patch to fix them.

If Skeleton Key does not act in the way you expect - please update to the [latest version][PROJECT].
If the problem persists do some research to determine if the error has already been discovered and addressed.
Try searching for the problem or error message on Google, if nothing comes up please feel free to create an [Issue][ISSUES]


network.py
===========
This framework component of Skeleton Key requires no user input and runs in the background. The script is never directly called by the user and is instead used to allow the following modules that have been developed by "Team" to operate:

	- Responder


Network Features
---------
- Turns the raspberry pi into an "ethernet" adapter using USB OTG functionality (emulation of a network device).
	- This "ethernet" adapter is recognised as usb0 under network devices on the pi.
	- It can be configured to appear as a specific type of "ethernet" adapter by editing "vendor_id" and "product_id" in the source
	code of this component.
	- From there the pi can be used to capture network traffic from a target over usb0.
	
Network Bugs
-----
As user interaction is pretty much non-existant with this componenent there is very little to worry about regarding bugs (that we have been able to find). Please note the following however:

- Due to how some target systems may be configured with regards to driver installation usb0 may fail to be recognised. As a result of this a little tinkering with the values "vendor_id" and "product_id" may have to ensue for network.py to work as intended. 



keyboard.py
===========
This framework component of Skeleton Key requries ducky scripts to operate. The functionality of Keyboard can be accessed through the Ducky Script Module by Users, or directly by Module Developers.

The way keyboard works is similar for both developers and users. Users will select a ducky script file through the interface which will then be used with keyboard.py, while developers can send a ducky script string containing their desired action to keyboard.

Keyboard Features
---------
- Turns the rapsberry pi into a USB Rubber Ducky (emulation of a Keyboard device)
- Can be used to enter text or perform complex key insertions
- Accepts ducky script and some things not supported in ducky script:
	- WIN SHIFT S  performs the same as WIN-SHIFT S
	- CTRL ALT DEL performs the same as CTRL-ALT-DELETE

Keyboard Bugs
-----
The ducky interpreter currently doesn't support F Numbers e.g. F12

	
Authors
-------
[Andrew Calder](https://github.com/AR-Calder) - [Email](1503321@uad.ac.uk)

[Corey Forbes](https://github.com/yeroc-sebrof) - [Email](1500812@uad.ac.uk)

[Ellis Richmond](https://github.com/EGRichmond) - [Email](1501363@uad.ac.uk)

[Jonathan Ross](https://github.com/Joh98) - [Email](1500598@uad.ac.uk)

[Michaela Stewart](https://github.com/muicheka) - [Email](1501125@uad.ac.uk)

[LOGO]: key.png
[BLINKT]: https://shop.pimoroni.com/products/blinkt "Pimoroni Link to Blinkt kit"
[USBSTEM]: https://shop.pimoroni.com/products/zero-stem-usb-otg-connector "Pimoroni Link to USB Stem"
[PROJECT]: https://github.com/AR-Calder/usbskeletonkey "Skeleton Key Project"
[ISSUES]: https://github.com/AR-Calder/usbskeletonkey/issues "Skeleton Key Issues Page"
[LEGAL]: LEGAL%20DISCLAIMER.pdf
