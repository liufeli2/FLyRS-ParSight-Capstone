# Flight Procedure

## Pre-Flight Checks
- Before launching, complete the following safety and setup steps:
- Ensure all wires are clear, the net is pulled, and the test area is secure.
- Confirm time synchronization between onboard and ground systems.
- Verify vision pose matches local position in RViz.
- Ensure Vicon data is streaming correctly and matches expectations.

## Flight Process
- Launch Camera Node and Detection Node.
- Wait for successful detection of the golf ball in the scene.
- Once confirmed, unkill, arm, and switch to Offboard mode.
- Launch ParSight node to begin visual tracking.
- Wait until drone reaches stable flying height, then begin the test.
- Trigger the catapult once the drone begins active tracking.
- The drone will hover over the ball once it detects the ball has come to rest.
- Land the drone and kill to complete the demo.

## General Troubleshooting
If issues arise during setup or flight:
- Relaunch the MAVROS node.
- Replug drone hardware connections.
- Reboot the Cube flight controller.
- Swap in a fully charged battery.
- Recalibrate sensors if alignment issues persist.
