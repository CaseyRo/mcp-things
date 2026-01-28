#!/bin/bash

# Define the full command
CMD="/Users/caseyromkes/things-fastmcp/.venv/bin/python /Users/caseyromkes/things-fastmcp/things_fast_server.py"

# Start using pm2 with a name
pm2 start "$CMD" --interpreter none --name things-fastmcp
