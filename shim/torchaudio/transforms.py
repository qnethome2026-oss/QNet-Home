import math, torch, torch.nn as nn
from scipy.signal import resample_poly
import numpy as np

class Resample(nn.Module):
    """Drop-in for torchaudio.transforms.Resample using scipy polyphase filtering."""
    def __init__(self, orig_freq=16000, new_freq=16000, **kw):
        super().__init__()
        self.orig_freq, self.new_freq = int(orig_freq), int(new_freq)
        g = math.gcd(self.orig_freq, self.new_freq)
        self.up, self.down = self.new_freq // g, self.orig_freq // g
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.orig_freq == self.new_freq: return x
        dev, dt = x.device, x.dtype
        a = x.detach().cpu().float().numpy()
        y = resample_poly(a, self.up, self.down, axis=-1)
        return torch.from_numpy(np.ascontiguousarray(y)).to(device=dev, dtype=dt)


# ---- Additional pure-torch transforms needed by resemble-perth's audio_processor ----
class Spectrogram(nn.Module):
    def __init__(self, n_fft=400, win_length=None, hop_length=None, pad=0,
                 window_fn=torch.hann_window, power=2.0, normalized=False,
                 wkwargs=None, center=True, pad_mode="reflect", onesided=True, **kw):
        super().__init__()
        self.n_fft = n_fft
        self.win_length = win_length or n_fft
        self.hop_length = hop_length or self.win_length // 2
        self.pad, self.power, self.normalized = pad, power, normalized
        self.center, self.pad_mode, self.onesided = center, pad_mode, onesided
        w = window_fn(self.win_length) if wkwargs is None else window_fn(self.win_length, **wkwargs)
        self.register_buffer("window", w)

    def forward(self, waveform):
        if self.pad > 0:
            waveform = torch.nn.functional.pad(waveform, (self.pad, self.pad), "constant")
        shape = waveform.size()
        wf = waveform.reshape(-1, shape[-1])
        spec = torch.stft(wf, self.n_fft, self.hop_length, self.win_length,
                          self.window.to(wf.dtype if wf.is_floating_point() else torch.float32),
                          center=self.center, pad_mode=self.pad_mode, normalized=False,
                          onesided=self.onesided, return_complex=True)
        spec = spec.reshape(shape[:-1] + spec.shape[-2:])
        if self.normalized:
            spec = spec / self.window.pow(2.0).sum().sqrt()
        if self.power is not None:
            if self.power == 1.0:
                return spec.abs()
            return spec.abs().pow(self.power)
        return spec


class InverseSpectrogram(nn.Module):
    def __init__(self, n_fft=400, win_length=None, hop_length=None, pad=0,
                 window_fn=torch.hann_window, normalized=False, wkwargs=None,
                 center=True, pad_mode="reflect", onesided=True, **kw):
        super().__init__()
        self.n_fft = n_fft
        self.win_length = win_length or n_fft
        self.hop_length = hop_length or self.win_length // 2
        self.pad, self.normalized = pad, normalized
        self.center, self.onesided = center, onesided
        w = window_fn(self.win_length) if wkwargs is None else window_fn(self.win_length, **wkwargs)
        self.register_buffer("window", w)

    def forward(self, spectrogram, length=None):
        shape = spectrogram.size()
        spec = spectrogram.reshape(-1, shape[-2], shape[-1])
        if self.normalized:
            spec = spec * self.window.pow(2.0).sum().sqrt()
        wf = torch.istft(spec, self.n_fft, self.hop_length, self.win_length,
                         self.window.to(torch.float32), center=self.center,
                         normalized=False, onesided=self.onesided, length=length)
        return wf.reshape(shape[:-2] + wf.shape[-1:])


def _phase_vocoder(complex_specgrams, rate, phase_advance):
    """Vendored logic of torchaudio.functional.phase_vocoder (pure torch)."""
    if rate == 1.0:
        return complex_specgrams
    shape = complex_specgrams.size()
    complex_specgrams = complex_specgrams.reshape([-1] + list(shape[-2:]))
    time_steps = torch.arange(0, complex_specgrams.size(-1), rate,
                              device=complex_specgrams.device,
                              dtype=torch.real(complex_specgrams).dtype)
    alphas = time_steps % 1.0
    phase_0 = complex_specgrams[..., :1].angle()
    complex_specgrams = torch.nn.functional.pad(complex_specgrams, [0, 2])
    cs0 = complex_specgrams.index_select(-1, time_steps.long())
    cs1 = complex_specgrams.index_select(-1, (time_steps + 1).long())
    angle_0, angle_1 = cs0.angle(), cs1.angle()
    norm_0, norm_1 = cs0.abs(), cs1.abs()
    phase = angle_1 - angle_0 - phase_advance
    phase = phase - 2 * math.pi * torch.round(phase / (2 * math.pi))
    phase = phase + phase_advance
    phase = torch.cat([phase_0, phase[..., :-1]], dim=-1)
    phase_acc = torch.cumsum(phase, -1)
    mag = alphas * norm_1 + (1 - alphas) * norm_0
    out = torch.polar(mag, phase_acc)
    return out.reshape(list(shape[:-2]) + list(out.shape[-2:]))


class TimeStretch(nn.Module):
    def __init__(self, hop_length=None, n_freq=201, fixed_rate=None, **kw):
        super().__init__()
        self.fixed_rate = fixed_rate
        hop = hop_length if hop_length is not None else (n_freq - 1)
        self.register_buffer("phase_advance",
                             torch.linspace(0, math.pi * hop, n_freq)[..., None])

    def forward(self, complex_specgrams, overriding_rate=None):
        rate = overriding_rate if overriding_rate is not None else self.fixed_rate
        if rate is None:
            raise ValueError("rate must be provided")
        return _phase_vocoder(complex_specgrams, rate, self.phase_advance)
