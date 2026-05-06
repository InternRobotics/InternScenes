"""MDL material reference helpers for Isaac Sim rendering."""

from __future__ import annotations

import os
from pathlib import Path

from pxr import Usd


def _read_file(path: str | Path) -> str:
    with open(path) as f:
        return f.read()


def _write_file(path: str | Path, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def _parse_asset_path(attr_value) -> tuple[bool, list[str] | None]:
    value = str(attr_value)
    if "@" in value and len(value) > 3:
        return True, value.split("@")
    return False, None


def _normalize_material_path(path: str) -> str:
    return path if "Materials" in path.split("/") else f"./Materials/{path}"


def _create_mdl_from_template(
    asset_path: str,
    template_content: str,
    placeholder: str = "Material__43",
) -> None:
    folder, filename = os.path.split(asset_path)
    os.makedirs(folder, exist_ok=True)
    material_name = filename.split(".")[0] or "Material"
    _write_file(asset_path, template_content.replace(placeholder, material_name))


def _ensure_mdl_file(
    asset_path: str,
    template_content: str,
    overwrite: bool,
) -> None:
    if not os.path.exists(asset_path):
        _create_mdl_from_template(asset_path, template_content)
    elif os.path.getsize(asset_path) < 1 and overwrite:
        _create_mdl_from_template(asset_path, template_content)


def _process_asset_attribute(
    attr: Usd.Attribute,
    base_path: str,
    template_content: str,
    overwrite: bool,
) -> bool:
    is_valid, names = _parse_asset_path(attr.Get())
    if not is_valid or names is None:
        return False
    if names[1] == "OmniPBR.mdl" or not names[1].endswith(".mdl"):
        return False

    names[1] = _normalize_material_path(names[1])
    asset_path = os.path.abspath(os.path.join(base_path, names[1]))
    _ensure_mdl_file(asset_path, template_content, overwrite)

    need_save = False
    if os.path.exists(asset_path):
        new_value = "@".join(names)
        if attr.Get() != new_value:
            attr.Set(new_value)
            need_save = True

    sub_id_attr = attr.GetPrim().GetAttribute("info:mdl:sourceAsset:subIdentifier")
    if sub_id_attr and sub_id_attr.IsValid():
        material_name = os.path.splitext(os.path.basename(asset_path))[0]
        if sub_id_attr.Get() != material_name:
            sub_id_attr.Set(material_name)
            need_save = True

    return need_save


def fix_mdls(
    usd_path: str | Path,
    default_mdl_path: str | Path,
    overwrite: bool = True,
    save_usd: bool = True,
) -> None:
    usd_path = str(usd_path)
    base_path = os.path.dirname(usd_path)
    stage = Usd.Stage.Open(usd_path)
    template_content = _read_file(default_mdl_path)
    need_save = False
    for prim in stage.TraverseAll():
        for attr in prim.GetAttributes():
            if attr.GetTypeName() == "asset":
                need_save |= _process_asset_attribute(attr, base_path, template_content, overwrite)
    if need_save and save_usd:
        stage.Save()


def _is_mdl_attribute(attr) -> bool:
    return (
        attr.GetTypeName() == "asset"
        or attr.GetName() == "info:mdl:sourceAsset:subIdentifier"
    )


def _set_mdl_attribute_to_default(
    attr,
    default_mdl_path: str | Path,
    default_png_path: str | Path,
) -> None:
    image_extensions = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif")
    if attr.GetTypeName() == "asset":
        is_valid, names = _parse_asset_path(attr.Get())
        if not is_valid or names is None:
            return
        asset_name = names[1]
        if asset_name != "OmniPBR.mdl":
            if asset_name.endswith(".mdl"):
                attr.Set(str(default_mdl_path))
            elif asset_name.endswith(image_extensions):
                attr.Set(str(default_png_path))
    elif attr.GetName() == "info:mdl:sourceAsset:subIdentifier":
        if "OmniPBR" not in attr.Get():
            attr.Set("WhiteMode")


def set_all_material_to_default(
    usd_stage: Usd.Stage,
    default_mdl_path: str | Path,
    default_png_path: str | Path,
) -> None:
    for prim in usd_stage.TraverseAll():
        for attr in prim.GetAttributes():
            if _is_mdl_attribute(attr):
                _set_mdl_attribute_to_default(attr, default_mdl_path, default_png_path)
