"""配置加载 - 读取 config.yaml 并提供全局配置访问"""

from pathlib import Path

# 配置文件搜索路径
_CONFIG_SEARCH_PATHS = [
    Path.cwd() / "config.yaml",
    Path(__file__).resolve().parent.parent.parent / "config.yaml",
    Path.home() / ".config" / "daylife" / "config.yaml",
]

# 默认配置
_DEFAULTS = {
    "database": {"path": None, "wal_mode": True},
    "web": {"host": "127.0.0.1", "port": 8063, "reload": False},
    "mcp": {"transport": "stdio"},
    "import": {"excel_path": "D:/my college/zyc学习计划/"},
    "display": {"date_format": "iso", "language": "zh", "page_size": 20},
    "export": {"output_dir": "./exports", "default_format": "markdown"},
}


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 优先"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str | Path | None = None) -> dict:
    """加载配置文件，返回合并后的配置字典"""
    if config_path:
        paths = [Path(config_path)]
    else:
        paths = _CONFIG_SEARCH_PATHS

    for p in paths:
        if p.exists():
            try:
                import yaml
                with open(p, encoding="utf-8") as f:
                    user_config = yaml.safe_load(f) or {}
                return _deep_merge(_DEFAULTS, user_config)
            except ImportError:
                # 没装 pyyaml，用简单的方式读
                break
            except Exception:
                break

    return _DEFAULTS.copy()


# 全局配置单例
_config: dict | None = None


def get_config() -> dict:
    """获取全局配置（懒加载）"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
