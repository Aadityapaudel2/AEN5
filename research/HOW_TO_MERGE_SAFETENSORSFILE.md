# How AthenaV1.29 Was Merged Into One `model.safetensors`

Date written: 2026-04-27

This note documents exactly what was done to merge the AthenaV1.29 sharded
Safetensors checkpoint into one coherent `model.safetensors` file.

The original model folder was not modified. A new sibling folder was created
for the merged copy.

## Short Version

The source model was here:

```text
D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29
```

It contained four sharded Safetensors weight files:

```text
model.safetensors-00001-of-00004.safetensors
model.safetensors-00002-of-00004.safetensors
model.safetensors-00003-of-00004.safetensors
model.safetensors-00004-of-00004.safetensors
```

It also contained the required index file:

```text
model.safetensors.index.json
```

The merged model was written here:

```text
D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged
```

The final merged weights file is:

```text
D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged\model.safetensors
```

The final merged file size was:

```text
19,306,313,184 bytes
```

Validation confirmed:

```text
tensor_count:   775
expected_count: 775
missing:        0
extra:          0
metadata:       {'format': 'pt'}
has_index:      False
```

So the merged file contains all expected tensors, no extra tensors, and no
shard index file was copied into the merged folder.

## What These Shards Are

The files named like this:

```text
model.safetensors-00001-of-00004.safetensors
```

are not four different models. They are four pieces of one model checkpoint.

Large Hugging Face / Transformers models are commonly split into shards so
that each individual file stays below a chosen size limit. The index file:

```text
model.safetensors.index.json
```

maps every tensor name to the shard file that stores it.

For example, the index says which shard contains tensors such as model layers,
embedding weights, norm weights, and output weights. Without the index, a
loader would not know where each tensor lives.

Merging means:

1. Read the shard index.
2. Open each shard.
3. Read each tensor's metadata and raw tensor bytes.
4. Build one new Safetensors header that describes all tensors.
5. Append all tensor bytes into one large `model.safetensors` file.
6. Copy the non-weight sidecar files, such as `config.json` and tokenizer
   files, into a new model folder.

## Important Result

The merged folder is a normal model folder with a single weight file:

```text
AthenaV1.29-merged\
  config.json
  model.safetensors
  tokenizer.json
  tokenizer_config.json
  vocab.json
  merges.txt
  chat_template.jinja
  README.md
  LICENSE
  .gitattributes
  preprocessor_config.json
  video_preprocessor_config.json
  memory_athena.ndjson
```

The merged folder intentionally does not contain:

```text
model.safetensors.index.json
model.safetensors-00001-of-00004.safetensors
model.safetensors-00002-of-00004.safetensors
model.safetensors-00003-of-00004.safetensors
model.safetensors-00004-of-00004.safetensors
```

That is deliberate. Once all weights are inside one file named
`model.safetensors`, there is no need for the old sharded index.

## Environment Check

Before merging, the local Python environment was checked.

The installed package versions were:

```text
torch==2.8.0
transformers==5.5.0
safetensors==0.7.0
```

The source folder was inspected and confirmed to contain these relevant files:

```text
.gitattributes
chat_template.jinja
config.json
LICENSE
memory_athena.ndjson
merges.txt
model.safetensors-00001-of-00004.safetensors
model.safetensors-00002-of-00004.safetensors
model.safetensors-00003-of-00004.safetensors
model.safetensors-00004-of-00004.safetensors
model.safetensors.index.json
preprocessor_config.json
README.md
tokenizer.json
tokenizer_config.json
video_preprocessor_config.json
vocab.json
```

The shard file sizes were:

```text
model.safetensors-00001-of-00004.safetensors  5,276,436,216 bytes
model.safetensors-00002-of-00004.safetensors  5,335,161,512 bytes
model.safetensors-00003-of-00004.safetensors  5,368,717,440 bytes
model.safetensors-00004-of-00004.safetensors  3,325,995,712 bytes
```

The index metadata reported:

```text
total_size: 19,306,216,416 bytes
tensor_count: 775
shards:
  model.safetensors-00001-of-00004.safetensors
  model.safetensors-00002-of-00004.safetensors
  model.safetensors-00003-of-00004.safetensors
  model.safetensors-00004-of-00004.safetensors
```

Disk space was also checked. Drive `D:` had about:

```text
52.61 GB free
```

That was enough because the merge needed to create one new file of about
18 GiB / 19.3 GB while leaving the original shards untouched.

## Why A Streaming Merge Was Used

There are two common ways to merge sharded Safetensors files.

The simple way is to load the full model with Transformers and then save it
again with a large shard size:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

src = r"path\to\sharded_model_folder"
dst = r"path\to\merged_model_folder"

model = AutoModelForCausalLM.from_pretrained(
    src,
    torch_dtype="auto",
    low_cpu_mem_usage=True,
    trust_remote_code=True,
)

tok = AutoTokenizer.from_pretrained(src, trust_remote_code=True)

model.save_pretrained(
    dst,
    safe_serialization=True,
    max_shard_size="50GB",
)

tok.save_pretrained(dst)
```

That method is easy, but it may require enough RAM or device memory to
instantiate the model object.

For this merge, a lower-memory streaming method was used instead.

The streaming method does not load the neural network as a Transformers model.
It directly reads the Safetensors files, reconstructs one combined Safetensors
header, and streams the raw tensor bytes into a new file.

That is useful because:

1. It avoids loading the entire model into RAM.
2. It preserves the original tensor bytes.
3. It keeps the original folder untouched.
4. It only needs enough disk space for the new merged file.

## Safetensors File Structure In Plain English

A `.safetensors` file has two major parts:

1. A JSON header.
2. Raw tensor byte data.

At the very beginning of the file there are 8 bytes that say how long the JSON
header is. After that comes the JSON header. After that comes the raw binary
tensor data.

Each tensor entry in the JSON header says:

```text
tensor name
dtype
shape
data_offsets
```

The `data_offsets` field tells the loader where that tensor's bytes begin and
end inside the data section of the file.

In a sharded model, each shard has its own header, and each tensor's offsets
are relative to that shard's own data section.

When merging, those offsets must be recalculated so they point to the correct
locations inside the one new merged file.

That is the key technical step.

## Exact Merge Process

The merge script did the following:

1. Set the source folder:

   ```text
   D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29
   ```

2. Set the destination folder:

   ```text
   D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged
   ```

3. Read:

   ```text
   model.safetensors.index.json
   ```

4. Extracted the `weight_map` from the index.

   The `weight_map` is the map from tensor name to shard filename.

5. Found the unique shard filenames:

   ```text
   model.safetensors-00001-of-00004.safetensors
   model.safetensors-00002-of-00004.safetensors
   model.safetensors-00003-of-00004.safetensors
   model.safetensors-00004-of-00004.safetensors
   ```

6. Created the destination folder if needed.

7. Copied sidecar files from the source folder to the destination folder.

   The script copied normal model files such as:

   ```text
   config.json
   tokenizer.json
   tokenizer_config.json
   vocab.json
   merges.txt
   chat_template.jinja
   README.md
   LICENSE
   ```

   The script deliberately did not copy the old sharded weight files or the old
   shard index file.

8. Opened every shard and read its Safetensors header.

9. Collected every tensor entry from every shard.

10. Verified that each tensor's shard matched the index.

    This means that if a tensor was found in shard 2, the index also had to say
    that the tensor belonged to shard 2.

11. Verified there were no duplicate tensor names.

12. Verified there were no missing or extra tensor names compared with the
    index.

13. Built a new single-file Safetensors header.

    The new header kept each tensor's:

    ```text
    name
    dtype
    shape
    ```

    But it recalculated:

    ```text
    data_offsets
    ```

    so every tensor points to its new location inside the one merged file.

14. Checked the total tensor byte count.

    The newly calculated total tensor bytes had to match the index metadata:

    ```text
    19,306,216,416 bytes
    ```

15. Wrote a temporary output file first.

    The temporary file had a name like:

    ```text
    model.safetensors.tmp-<process_id>
    ```

    This avoids leaving a half-valid final `model.safetensors` if the merge is
    interrupted.

16. Wrote the new Safetensors header to the temporary file.

17. Streamed tensor bytes from the old shards into the temporary file.

    The script used 64 MiB chunks:

    ```text
    64 * 1024 * 1024 bytes
    ```

    This means it copied large blocks efficiently without reading the whole
    model into memory.

18. Replaced the temporary file with the final file:

    ```text
    model.safetensors
    ```

19. Checked the final output file size against the expected size:

    ```text
    final_size == 8 + header_bytes + tensor_bytes
    ```

20. Reported success.

## Exact Merge Script Used

This is the full Python merge script that was run locally.

It was run from:

```text
D:\AthenaPlayground
```

The script itself was passed directly to Python through PowerShell.

```python
from pathlib import Path
import json
import os
import shutil
import struct
import time

src = Path(r"D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29")
dst = Path(r"D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged")
index_path = src / "model.safetensors.index.json"
out_path = dst / "model.safetensors"
chunk_size = 64 * 1024 * 1024

if not src.is_dir():
    raise SystemExit(f"source folder not found: {src}")
if not index_path.exists():
    raise SystemExit(f"index file not found: {index_path}")
if out_path.exists():
    raise SystemExit(f"refusing to overwrite existing output: {out_path}")

dst.mkdir(parents=True, exist_ok=True)

index = json.loads(index_path.read_text(encoding="utf-8"))
weight_map = index.get("weight_map") or {}
if not weight_map:
    raise SystemExit("index has no weight_map")
shard_names = sorted(set(weight_map.values()))
expected_total = int((index.get("metadata") or {}).get("total_size") or 0)

# Copy model sidecar files, leaving out the sharded weight files and their index.
for item in src.iterdir():
    if not item.is_file():
        continue
    if item.name == "model.safetensors.index.json":
        continue
    if item.name.startswith("model.safetensors-") and item.name.endswith(".safetensors"):
        continue
    shutil.copy2(item, dst / item.name)

segments = []
shard_headers = {}
metadata = {"format": "pt"}
seen = set()

for shard_name in shard_names:
    shard_path = src / shard_name
    if not shard_path.exists():
        raise SystemExit(f"missing shard: {shard_path}")
    with shard_path.open("rb") as f:
        n_raw = f.read(8)
        if len(n_raw) != 8:
            raise SystemExit(f"bad safetensors header length in {shard_name}")
        header_len = struct.unpack("<Q", n_raw)[0]
        header_bytes = f.read(header_len)
        header = json.loads(header_bytes)
    shard_headers[shard_name] = header_len
    if "__metadata__" in header and isinstance(header["__metadata__"], dict):
        metadata.update(header["__metadata__"])
    tensor_items = [(name, spec) for name, spec in header.items() if name != "__metadata__"]
    tensor_items.sort(key=lambda kv: kv[1]["data_offsets"][0])
    for name, spec in tensor_items:
        mapped = weight_map.get(name)
        if mapped != shard_name:
            raise SystemExit(f"index mismatch for {name}: header in {shard_name}, index says {mapped}")
        if name in seen:
            raise SystemExit(f"duplicate tensor name: {name}")
        begin, end = spec["data_offsets"]
        if end < begin:
            raise SystemExit(f"bad offsets for {name}")
        segments.append({
            "name": name,
            "shard": shard_name,
            "begin": int(begin),
            "end": int(end),
            "dtype": spec["dtype"],
            "shape": spec["shape"],
        })
        seen.add(name)

missing = set(weight_map) - seen
extra = seen - set(weight_map)
if missing or extra:
    raise SystemExit(f"tensor set mismatch: missing={len(missing)}, extra={len(extra)}")

merged_header = {"__metadata__": metadata}
offset = 0
for seg in segments:
    size = seg["end"] - seg["begin"]
    merged_header[seg["name"]] = {
        "dtype": seg["dtype"],
        "shape": seg["shape"],
        "data_offsets": [offset, offset + size],
    }
    offset += size

if expected_total and offset != expected_total:
    raise SystemExit(f"total byte mismatch: merged={offset}, index={expected_total}")

header_bytes = json.dumps(merged_header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
header_bytes += b" " * ((8 - (len(header_bytes) % 8)) % 8)

tmp_path = dst / f"model.safetensors.tmp-{os.getpid()}"
start = time.time()
written = 0

print(f"copying sidecars to {dst}")
print(f"writing {len(segments)} tensors from {len(shard_names)} shards")
print(f"tensor bytes: {offset}")
print(f"header bytes: {len(header_bytes)}")

with tmp_path.open("wb") as out:
    out.write(struct.pack("<Q", len(header_bytes)))
    out.write(header_bytes)
    current_shard = None
    current_file = None
    try:
        for i, seg in enumerate(segments, 1):
            if seg["shard"] != current_shard:
                if current_file is not None:
                    current_file.close()
                current_shard = seg["shard"]
                current_file = (src / current_shard).open("rb")
                print(f"streaming {current_shard}")
            absolute = 8 + shard_headers[current_shard] + seg["begin"]
            remaining = seg["end"] - seg["begin"]
            current_file.seek(absolute)
            while remaining:
                data = current_file.read(min(chunk_size, remaining))
                if not data:
                    raise SystemExit(f"unexpected EOF while reading {seg['name']}")
                out.write(data)
                remaining -= len(data)
                written += len(data)
            if i % 100 == 0 or i == len(segments):
                elapsed = max(time.time() - start, 0.001)
                gb = written / (1024 ** 3)
                print(f"  {i}/{len(segments)} tensors, {gb:.2f} GiB, {gb/elapsed:.2f} GiB/s")
    finally:
        if current_file is not None:
            current_file.close()

os.replace(tmp_path, out_path)
final_size = out_path.stat().st_size
expected_size = 8 + len(header_bytes) + offset
if final_size != expected_size:
    raise SystemExit(f"final size mismatch: got={final_size}, expected={expected_size}")

print(f"done: {out_path}")
print(f"final size: {final_size}")
```

## Merge Output Log

The merge completed successfully.

The local run printed:

```text
copying sidecars to D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged
writing 775 tensors from 4 shards
tensor bytes: 19306216416
header bytes: 96760
streaming model.safetensors-00001-of-00004.safetensors
streaming model.safetensors-00002-of-00004.safetensors
streaming model.safetensors-00003-of-00004.safetensors
  100/775 tensors, 12.48 GiB, 0.15 GiB/s
streaming model.safetensors-00004-of-00004.safetensors
  200/775 tensors, 15.04 GiB, 0.15 GiB/s
  300/775 tensors, 15.97 GiB, 0.15 GiB/s
  400/775 tensors, 16.85 GiB, 0.15 GiB/s
  500/775 tensors, 17.25 GiB, 0.15 GiB/s
  600/775 tensors, 17.48 GiB, 0.15 GiB/s
  700/775 tensors, 17.72 GiB, 0.15 GiB/s
  775/775 tensors, 17.98 GiB, 0.15 GiB/s
done: D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged\model.safetensors
final size: 19306313184
```

The progress jumps are normal. Large tensors dominate the byte count, so the
number of tensors processed does not increase linearly with file size.

## Why Final Size Is Slightly Larger Than Tensor Bytes

The tensor byte count from the index was:

```text
19,306,216,416 bytes
```

The final file size was:

```text
19,306,313,184 bytes
```

The final file is slightly larger because a Safetensors file also contains:

1. 8 bytes at the beginning for the header length.
2. The JSON header itself.
3. Padding added to align the header.

For this merged file:

```text
header bytes: 96,760
```

So:

```text
8 + 96,760 + 19,306,216,416 = 19,306,313,184
```

That exactly matches the final output file size.

## Validation Step 1: Inspect Output Folder

After the merge, the output folder contained:

```text
.gitattributes
chat_template.jinja
config.json
LICENSE
memory_athena.ndjson
merges.txt
model.safetensors
preprocessor_config.json
README.md
tokenizer.json
tokenizer_config.json
video_preprocessor_config.json
vocab.json
```

The output folder did not contain:

```text
model.safetensors.index.json
model.safetensors-00001-of-00004.safetensors
model.safetensors-00002-of-00004.safetensors
model.safetensors-00003-of-00004.safetensors
model.safetensors-00004-of-00004.safetensors
```

That is the expected structure for a single-file Safetensors model.

## Validation Step 2: Open The Merged File With `safetensors`

The merged file was opened with the Safetensors library without loading all
tensors into memory.

Validation command:

```powershell
python -c "from pathlib import Path; import json; from safetensors import safe_open; src=Path(r'D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29'); dst=Path(r'D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged'); idx=json.loads((src/'model.safetensors.index.json').read_text()); expected=set(idx['weight_map']); f=safe_open(dst/'model.safetensors', framework='pt', device='cpu'); keys=set(f.keys()); print('opened', dst/'model.safetensors'); print('tensor_count', len(keys)); print('expected_count', len(expected)); print('missing', len(expected-keys)); print('extra', len(keys-expected)); print('metadata', f.metadata()); print('has_index', (dst/'model.safetensors.index.json').exists())"
```

Validation output:

```text
opened D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged\model.safetensors
tensor_count 775
expected_count 775
missing 0
extra 0
metadata {'format': 'pt'}
has_index False
```

This confirms that:

1. The merged file is readable.
2. All 775 tensors from the original index exist in the merged file.
3. No tensors are missing.
4. No extra tensors were introduced.
5. The merged folder is not still pointing at the old shard index.

## Validation Step 3: Check Transformers Config And Tokenizer

The full model weights were not loaded into Transformers for this final check.
Only the config and tokenizer were loaded.

Validation command:

```powershell
python -c "from transformers import AutoConfig, AutoTokenizer; p=r'D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged'; cfg=AutoConfig.from_pretrained(p, trust_remote_code=True); tok=AutoTokenizer.from_pretrained(p, trust_remote_code=True); print('model_type', getattr(cfg, 'model_type', None)); print('architectures', getattr(cfg, 'architectures', None)); print('tokenizer', tok.__class__.__name__); print('vocab_size', getattr(tok, 'vocab_size', None))"
```

Validation output:

```text
model_type qwen3_5
architectures ['Qwen3_5ForConditionalGeneration']
tokenizer TokenizersBackend
vocab_size 248044
```

This confirms that the merged folder still looks like a valid Transformers
model directory at the config/tokenizer level.

## What Was Not Done

The original folder was not deleted or modified:

```text
D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29
```

The old shard files were left intact.

The model was not converted to GGUF.

The model was not quantized.

The model was not fine-tuned.

The model weights were not changed mathematically.

This was only a packaging/layout change:

```text
four shard files + one shard index
```

became:

```text
one model.safetensors file
```

## How To Use The Merged Model Folder

Point loaders at:

```text
D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged
```

not directly at the `.safetensors` file.

Most Transformers-style loaders expect a folder containing:

```text
config.json
tokenizer files
model.safetensors
```

Example:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_dir = r"D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged"

tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_dir,
    torch_dtype="auto",
    trust_remote_code=True,
)
```

Depending on available hardware and the exact model architecture, loading the
full model may require additional arguments such as `device_map`, quantization,
or a runtime like vLLM/SGLang.

## How To Repeat This Safely

If repeating this process for another sharded model, follow this checklist.

1. Make sure the source folder has:

   ```text
   model.safetensors.index.json
   model.safetensors-00001-of-xxxxx.safetensors
   model.safetensors-00002-of-xxxxx.safetensors
   ...
   config.json
   tokenizer files
   ```

2. Make sure there is enough free disk space for the new merged file.

   A safe rule is:

   ```text
   free space >= total shard size + a few extra GB
   ```

3. Write to a new destination folder.

   Do not overwrite the source folder during the first merge.

4. Do not copy the old shard index into the merged folder.

5. Validate the merged file with `safe_open`.

6. Confirm the tensor count matches the original index.

7. Confirm missing and extra tensor counts are both zero.

8. Load the config and tokenizer from the merged folder.

9. Only after validation should downstream apps be pointed at the merged folder.

## Common Mistakes

Mistake:

```text
Copying the four shard files into one file with a normal binary concat command.
```

Why that is wrong:

Each shard has its own Safetensors header. Simple concatenation would create a
file with multiple independent headers and invalid offsets. A valid merged file
needs one new header with recalculated offsets.

Mistake:

```text
Keeping model.safetensors.index.json next to the merged model.safetensors.
```

Why that can be confusing:

Some loaders may see the index and expect sharded files. For a single-file
layout, the clean folder should contain `model.safetensors` and no shard index.

Mistake:

```text
Deleting the original shards before validating the merged file.
```

Why that is risky:

If the merge is interrupted or the output file is incomplete, the original
shards are needed to retry.

Mistake:

```text
Loading the full model into RAM just to re-save it.
```

Why that can be unnecessary:

A streaming merge can combine the files without instantiating the neural
network. This is usually safer for large checkpoints.

## Final Status

The AthenaV1.29 sharded Safetensors checkpoint was successfully merged into:

```text
D:\AthenaPlayground\AthenaV5\exclusive\AthenaV1.29-merged\model.safetensors
```

The merged file opened successfully with the Safetensors library.

All expected tensor names were present.

No tensor names were missing.

No unexpected tensor names were added.

The folder's config and tokenizer were readable through Transformers.

The original sharded model folder was left untouched.
