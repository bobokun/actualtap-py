#!/bin/sh

# Download latest config files if they don't exist or are different
file="config.yml.sample"
local_file="$CONFIG_DIR/$file"
latest_file="/app/config/$file"

if [ ! -f "$local_file" ] || ! diff -q "$latest_file" "$local_file" > /dev/null 2>&1; then
    echo "Copying latest $file"
    cp "$latest_file" "$local_file"
    chmod -R 777 /${local_file} > /dev/null 2>&1
else
    echo "File $file is up to date"
fi

# Execute the main command
exec "$@"
