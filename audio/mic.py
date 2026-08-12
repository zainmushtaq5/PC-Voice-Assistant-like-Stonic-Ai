"""Best-effort microphone management (unmute + level) using the Windows Core Audio API via pycaw."""


def ensure_mic_unmuted(level: float = 0.85):
    """Unmute the default microphone and, if its level is very low, raise it."""
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.api.endpointvolume import IAudioEndpointVolume
        from pycaw.pycaw import AudioUtilities

        dev = AudioUtilities.GetMicrophone()
        if dev is None:
            return
        vol = cast(
            dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
            POINTER(IAudioEndpointVolume),
        )
        if vol.GetMute():
            vol.SetMute(0, None)
            print("[Mic] Microphone was muted -> unmuted.")
        if vol.GetMasterVolumeLevelScalar() < 0.5:
            vol.SetMasterVolumeLevelScalar(level, None)
            print("[Mic] Microphone level raised.")
    except Exception as exc:
        print(f"[Mic] Could not auto-manage microphone: {exc}")
