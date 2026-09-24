from pathlib import Path
import asyncio
import hashlib
import os
import secrets

import aiohttp
from aiohttp import web
import folder_paths
from server import PromptServer


WEB_DIR = Path(__file__).resolve().parent / "web"
_LORA_PATHS = [Path(path) for path in folder_paths.get_folder_paths("loras")]
LORA_DIR = _LORA_PATHS[0] if _LORA_PATHS else Path(folder_paths.models_dir) / "loras"
LORA_DIR.mkdir(parents=True, exist_ok=True)
routes = PromptServer.instance.routes

GITHUB_RELEASE_API = (
    "https://api.github.com/repos/shuichisaitofd/h3-lora-assets/"
    "releases/tags/h3-loras-v1"
)
MANAGED_LORA_SPECS = {
    "BJ_v3.safetensors": "fbb93a67b429c79145c95598e9ac38388ad49d6df1c09c96cf989cce99277d53",
    "deepthroat_v02.safetensors": "1fd239662f6290255b0bb3a220764fb53aab2859378f7fd3024030c1e1991cb2",
    "Finger_BEAN_v1.safetensors": "914e3ecb0b515ad1a40c0185a8d23a34f87a1ced370db8bfb0ed3b5845dbf0a2",
    "HMCumshot_V2.safetensors": "1a5b7948bb97f27737e62c3dd5497a3afb77517f230787f45e45c7d8fe3dc24d",
    "Motion_FL2VA_v2.safetensors": "f6a6897162b921d2b74abe1fdebcd80c8189147e70e0e0738200756c250336c3",
    "Mystic_FL2VA_v4.safetensors": "fc3e856d14c6c19557c888f48662d591e4794e281233ec0d987be5003068afba",
    "Nipple_v2.safetensors": "7c30c92178e01e33cfbc4684a7b3fb1b71368293443b2941a5b889db3fbd3b18",
    "Orgasm_Masturbate_v1.4.safetensors": "3216dedb116e8da8f343bde4551001dd39b2e84d2392af9766d6380ea24007c7",
    "Panties_v1.safetensors": "f2bf0b4fc7d0ab6f3f91300b0a810dcd76e61f6e8fe39f7dbbd480245987447f",
    "Passionate_Kiss.safetensors": "71b3435525ef8907d35f12cfb9cb81ee9931761ecb27039fc6919b55dd8cda75",
    "Penis_HM_v2.safetensors": "017dd1adddc1be3ec0605dd2e7de97138eb2c6c6ba24be402cf47f103ac1f1b3",
    "Pussy_HM_v1.safetensors": "373c3cad3bf27047fdd754fe111443d97e70e3108a8829f2ec63c48832466eb3",
    "Squirt_HM_v2.safetensors.safetensors": "f0e4bfbe5baebe972880d2250a227e2f475aa8c18d6d01ed897288d9741659d2",
    "MM-H3.-.Fingering.v4.safetensors": "02b1fe9e5df8588cce1424c7bffb8a3fbb2c89e719a9af7fbbfd939b3d6caf87",
    "Cumshot_HM_v1.safetensors": "634c39cfcbfd9421a2d7b5adc62573fc232384c4c75e003c2e11d3408ad0765c",
    "Deepthroat_Ultimate_v1.safetensors": "c94e43ba18cb1e7d6dc5b376821bf593a997f60b09b662a2c5fc5b6a4bfb6105",
    "Finger_Insert_3323149.safetensors": "2f69376ce473d8a9a9ba4e3b306fabfc65c8d9252decff06f413d73741533540",
    "JerkOff_H3.safetensors": "d9145b17a8eca7fe252cb1c2a51e64745484df819db9bce0f90699263800e8aa",
    "M3_Unlocked_v2.safetensors": "8138e5ec1c6cc79706f1129311e90dcd04cc0ef708336c494161b09057f34c07",
}
