from pathlib import Path
from typing import Optional

from utils import get_server_config, save_server_config


def load_dashboard_rows(active_bot: Optional[object]) -> list[dict]:
    rows: list[dict] = []
    config_dir = Path("configs")
    guilds = {}
    guild_ids: set[str] = set()

    if active_bot and getattr(active_bot, "guilds", None):
        guilds = {str(g.id): g for g in active_bot.guilds}
        guild_ids.update(guilds.keys())

    if config_dir.exists():
        for config_file in sorted(config_dir.glob("*.json")):
            guild_ids.add(config_file.stem)

    for gid in sorted(guild_ids, key=int):
        cfg = get_server_config(gid)
        guild = guilds.get(gid)
        channels = sorted((guild.text_channels if guild else []), key=lambda c: c.position)
        channel_options = [{"id": str(ch.id), "name": ch.name} for ch in channels]

        rows.append(
            {
                "guild_id": gid,
                "guild_name": guild.name if guild else f"Guild {gid}",
                "notify_channel_id": str(cfg.get("notify_channel_id") or ""),
                "join_here_channel_name": cfg.get("join_here_channel_name") or "",
                "channel_options": channel_options,
                "selected_exempt_channels": {
                    str(ch_id) for ch_id in cfg.get("exempt_channels", [])
                },
                "exempt_guild": bool(cfg.get("exempt_guild", False)),
            }
        )
    return rows


def save_dashboard_config(
    guild_id: str,
    notify_raw: str,
    join_here: str,
    exempt_channel_ids: list[str],
    exempt_guild_enabled: bool,
) -> None:
    cfg = get_server_config(guild_id)
    cfg["notify_channel_id"] = int(notify_raw) if notify_raw.isdigit() else None
    cfg["join_here_channel_name"] = join_here or None
    cfg["exempt_channels"] = [
        int(ch_id) for ch_id in exempt_channel_ids if ch_id.isdigit()
    ]
    cfg["exempt_guild"] = exempt_guild_enabled
    save_server_config(guild_id, cfg)
