# Tool Guidance

## echo

Use `echo` only when the user explicitly asks for an exact repeated phrase or a short operational marker.

## read_file

Use `read_file` when:

- the user asks what a file currently contains
- the user asks for the current state of an artifact
- the task depends on current file contents
- a verification step requires reading the result back

Do not use `read_file` on memory-only turns.

## write_file

Use `write_file` when:

- the user wants a new file created
- the user wants an existing file fully replaced
- the task calls for a compact artifact with controlled contents

Do not use `write_file` when the user asked only for inspection.

## list_files

Use `list_files` when the user asks for workspace inventory, file discovery, or newly created artifact enumeration.

Do not confuse `list_files` with content inspection. Listing names is not the same as reading current contents.

## append_file

Use `append_file` when the user asks for:

- one short additional line
- dated log-style additions
- preserving prior file contents while adding a new entry

Do not use `append_file` if the user asked for a clean replacement artifact.

## get_date

Use `get_date` when the task depends on today's date and the turn expects grounded current-date usage.

If a turn is explicitly memory-only and the date is already a confirmed anchored session fact, recall may be acceptable. Otherwise prefer `get_date`.

## add_item

Use `add_item` when a new tracker task is implied and should appear in the bounded list state.

## update_item

Use `update_item` when an existing tracker item wording changes and the item identity should be preserved.

Prefer updating over deleting and recreating when the task is a wording change.

## read_list

Use `read_list` when the user refers to:

- the tracker
- current tracker contents
- current list state

`read_list` is authoritative for the bounded tracker state. `todo.txt` is not the same thing.

## finish

Use `finish` only on checkpoint or final wrap turns that explicitly require completion signaling.

Do not call `finish` on ordinary informational turns.
