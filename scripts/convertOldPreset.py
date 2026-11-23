"""Convert legacy web-mmd Default_data.json + Default_config.json into the
demo preset format consumed by the new app via APP_CONFIG.demoPresetUrl.

The new app's migratePreset() fetches this file and picks:
  - from useConfigStore: motionFiles, cameraFiles, pmxFiles, audioFiles
  - from usePresetStore:  every key present in Default_config.json

Usage:
  python3 scripts/convertOldPreset.py /path/to/old/web-mmd [audio-file]

If audio-file is given, it is embedded into audioFiles under the legacy
musicName, so the MV plays out of the box (the legacy preset only had a
YouTube URL, which the new player no longer supports).
"""
import base64
import json
import mimetypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_ROOT = os.path.dirname(HERE)


def main():
    if len(sys.argv) < 2:
        print("usage: convertOldPreset.py <old web-mmd root> [audio-file]")
        sys.exit(1)
    old_root = sys.argv[1]
    audio_path = sys.argv[2] if len(sys.argv) > 2 else None

    with open(os.path.join(old_root, "public/presets/Default_data.json"), encoding="utf-8") as f:
        old_data = json.load(f)
    with open(os.path.join(old_root, "public/presets/Default_config.json"), encoding="utf-8") as f:
        old_config = json.load(f)
    with open(os.path.join(NEW_ROOT, "app/presets/Default_config.json"), encoding="utf-8") as f:
        new_config = json.load(f)

    # --- ConfigState resources -------------------------------------------------
    # New: motionFiles / cameraFiles are {name: dataURI}
    motion_name = old_config["motion"]
    camera_name = old_config["camera"]

    motion_files = {motion_name: old_data["motionFile"]}
    camera_files = {camera_name: old_data["cameraFile"]}

    # The new player only consumes audioFiles[musicName] as a data URI.
    # Legacy preset had no audio embedded, so optionally inline one here.
    music_name = old_config["musicName"]
    audio_files = {}
    if audio_path:
        mime = mimetypes.guess_type(audio_path)[0] or "audio/mpeg"
        with open(audio_path, "rb") as f:
            audio_uri = "data:" + mime + ";base64," + base64.b64encode(f.read()).decode("ascii")
        audio_files[music_name] = audio_uri

    # New: pmxFiles = { models: {name: dataURI}, modelTextures: {folder: {path: dataURI}} }
    models = {}
    model_textures = {}
    for group in ("character", "stage"):
        for pmx_name, data_uri in old_data["pmxFiles"][group].items():
            models[pmx_name] = data_uri
        for pmx_name, textures in old_data["pmxFiles"]["modelTextures"][group].items():
            # Model.tsx derives folderName via fileName.split("/")[0]; the old
            # pmx names have no slash, so the pmx name itself is the folder key.
            model_textures[pmx_name] = textures

    # --- PresetState config ----------------------------------------------------
    preset = dict(new_config)  # start from new defaults for forward-compatible keys

    character = old_config["character"]
    stage = old_config["stage"]

    # Each model needs a stable id; models[id].fileName points into pmxFiles.models
    preset["models"] = {
        "character": {
            "fileName": character,
            "motionNames": [motion_name],
            "enableMorph": True,
            "enablePhysics": True,
            "enableMaterial": True,
        },
        "stage": {
            "fileName": stage,
            "motionNames": [],
            "enableMorph": False,
            "enablePhysics": False,
            "enableMaterial": False,
        },
    }
    preset["targetModelId"] = "character"
    preset["camera"] = camera_name
    preset["run mode"] = 0  # PLAYER_MODE
    preset["camera mode"] = 0  # MOTION_FILE -> uses cameraFiles[camera]
    preset["musicURL"] = ""
    preset["musicName"] = music_name

    # Copy over any config keys the new default also understands, mapping the ones
    # whose representation changed. Everything else stays at new defaults.
    if old_config.get("volume") is not None:
        preset["volume"] = old_config["volume"]
    if old_config.get("fov") is not None:
        preset["fov"] = old_config["fov"]
    if old_config.get("near") is not None:
        preset["near"] = old_config["near"]
    if old_config.get("gravity") is not None:
        preset["gravity"] = old_config["gravity"]

    # Assemble the single demo preset document.
    merged = {**preset}
    merged["motionFiles"] = motion_files
    merged["cameraFiles"] = camera_files
    merged["pmxFiles"] = {"models": models, "modelTextures": model_textures}
    merged["audioFiles"] = audio_files

    out_dir = os.path.join(NEW_ROOT, "public/presets")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "Default_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, separators=(",", ":"))

    print("wrote", out_path)
    print("  models:", list(models.keys()))
    print("  motionFiles:", list(motion_files.keys()))
    print("  cameraFiles:", list(camera_files.keys()))
    print("  audioFiles:", list(audio_files.keys()))
    print("  size MB:", round(os.path.getsize(out_path) / 1024 / 1024, 2))


if __name__ == "__main__":
    main()
