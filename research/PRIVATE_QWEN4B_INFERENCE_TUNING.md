# Private Qwen 3.5 4B Inference Tuning

## Scope

This note records a private-only inference profile that improved coherence and reduced repetition for the exclusive Athena desktop.

It is an inference result, not a training result.

## Working Profile

```json
{
  "temperature": 0.25,
  "max_new_tokens": 1024,
  "top_p": 0.75,
  "top_k": 16,
  "repetition_penalty": 1.15,
  "no_repeat_ngram_size": 8
}
```

## Observed Result

- coherence improved
- repetition behavior became acceptable
- this profile is a stronger private fallback than the hotter settings previously used

## Interpretation

The main gains likely came from:

- lower temperature
- lower top-p
- lower top-k
- shorter output budget

Together these reduced late-turn drift and repetitive tail generation.

## Use

This note should be treated as the current private anti-repeat baseline for the exclusive Athena route unless a later profile clearly outperforms it.
