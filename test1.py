from fireredasr.models.fireredasr import FireRedAsr
import torch
import argparse
torch.serialization.add_safe_globals([argparse.Namespace])

batch_uttid = ["BAC009S0764W0121"]
batch_wav_path = ["audio/test8.wav"]

# FireRedASR-AED
model = FireRedAsr.from_pretrained("aed", "FireRedTeam/FireRedASR-AED-L")
results = model.transcribe(
    batch_uttid,
    batch_wav_path,
    {
        "use_gpu": 1,
        "beam_size": 3,
        "nbest": 1,
        "decode_max_len": 0,
        "softmax_smoothing": 1.0,
        "aed_length_penalty": 0.0,
        "eos_penalty": 1.0
    }
)
print(results)