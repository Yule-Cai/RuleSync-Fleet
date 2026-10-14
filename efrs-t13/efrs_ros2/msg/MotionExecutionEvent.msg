# Fence verdict record (see msgspec.motion_event_msg for wire use).
string robot
string cmd_id
uint64 required_epoch
string verdict
string reason
builtin_interfaces/Time t_mono
