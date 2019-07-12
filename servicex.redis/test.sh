xadd mystream * ev1 asdfasdf
xadd mystream * ev2 aasdfsdfasdf
xadd mystream * ev3 aasdfsdfasdf
xlen mystream 

XREAD COUNT 2 STREAMS mystream 0

# $ means "starting from last message"

XGROUP CREATE mystream mygroup 0

XREADGROUP GROUP mygroup Alice COUNT 1 STREAMS mystream >

# > means "get messages that were never delivered to any other consumer in the group"

# acknowledge message
XACK mystream mygroup 1526569495631-0  

# shows messages not ack-ed
XPENDING mystream mygroup

# info
XINFO STREAM mystream

XINFO GROUPS mystream

XINFO CONSUMERS mystream mygroup 
