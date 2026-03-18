# Exclusive Desktop Text Attachments

## Scope

This note records the private-only `.txt` attachment path added to the exclusive desktop.

The goal is narrow on purpose:

- no public/browser changes
- no shared runtime changes
- no new retrieval subsystem yet
- the exclusive desktop can now accept local `.txt` files and feed their contents into the private model turn

## Implementation

Active UI file:

- `exclusive/desktop_app/main.py`

Behavior:

1. The exclusive desktop now exposes an `Add File` button alongside `Add Image`.
2. The file picker currently accepts `.txt` only.
3. Selected text files are tracked as pending attachments in the private desktop session.
4. The visible transcript stays clean:
   - it shows file markers and filenames
   - it does not dump full file contents into the visible chat transcript
5. The private model receives the file contents inline inside the submitted prompt for that turn.

## Prompt Assembly Model

For each attached text file, the desktop composes a bounded block:

- file name
- decoded text content
- explicit end marker

This is appended to the user turn before submission to the private runtime.

This is currently a direct inline attachment model, not retrieval.

## Safety / Practical Boundaries

- `.txt` only for the first pass
- text is read locally on the desktop side
- content is bounded before injection to reduce UI and context blowups
- transcript cleanliness is preserved by showing filenames instead of raw file contents

Current bound:

- `TEXT_ATTACHMENT_CHAR_LIMIT = 24000` per text file

If a file exceeds the bound, the injected content is truncated and tagged as truncated.

## Why This Path Was Chosen

This is the lowest-risk private-only implementation because it:

- avoids touching the public portal
- avoids touching the shared/public runtime path
- does not require a vector store or memory index
- keeps the private route self-contained

## Validation Status

Validated in code-level smoke checks:

- Python compile passed for `exclusive/desktop_app/main.py`
- prompt assembly smoke confirmed `.txt` content is injected into the private prompt
- visible transcript path remains filename-based rather than content-dumping

## Next Step

If this attachment path remains useful, the next private-only upgrade would be:

1. richer file metadata in the transcript
2. chunked file reading for larger text corpora
3. retrieval-style selective recall rather than full inline injection

For now, the design stays simple and local.
