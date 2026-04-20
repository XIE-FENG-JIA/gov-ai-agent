import os
import tempfile
import zipfile
from xml.etree import ElementTree as ET

CUSTOM_PROPERTY_FMTID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"
CUSTOM_PROPERTY_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties"
)
CUSTOM_PROPERTY_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.custom-properties+xml"
CONTENT_TYPES_XML_PATH = "[Content_Types].xml"
PACKAGE_RELS_XML_PATH = "_rels/.rels"
CUSTOM_PROPERTIES_NS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
DOC_PROPS_VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
PACKAGE_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CUSTOM_PROPERTIES_XML_PATH = "docProps/custom.xml"

ET.register_namespace("cp", CUSTOM_PROPERTIES_NS)
ET.register_namespace("vt", DOC_PROPS_VT_NS)
ET.register_namespace("", CONTENT_TYPES_NS)
ET.register_namespace("", PACKAGE_RELS_NS)


def build_custom_properties_xml(properties: dict[str, object]) -> bytes:
    root = ET.Element(f"{{{CUSTOM_PROPERTIES_NS}}}Properties")
    for pid, (name, value) in enumerate(properties.items(), start=2):
        prop = ET.SubElement(
            root,
            f"{{{CUSTOM_PROPERTIES_NS}}}property",
            {"fmtid": CUSTOM_PROPERTY_FMTID, "pid": str(pid), "name": name},
        )
        if isinstance(value, bool):
            child = ET.SubElement(prop, f"{{{DOC_PROPS_VT_NS}}}bool")
            child.text = "true" if value else "false"
        elif isinstance(value, int):
            child = ET.SubElement(prop, f"{{{DOC_PROPS_VT_NS}}}i4")
            child.text = str(value)
        else:
            child = ET.SubElement(prop, f"{{{DOC_PROPS_VT_NS}}}lpwstr")
            child.text = str(value)
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def ensure_content_types_custom_override(content_types_xml: bytes) -> bytes:
    root = ET.fromstring(content_types_xml)
    override_xpath = f"{{{CONTENT_TYPES_NS}}}Override"
    exists = any(node.get("PartName") == f"/{CUSTOM_PROPERTIES_XML_PATH}" for node in root.findall(override_xpath))
    if not exists:
        ET.SubElement(
            root,
            override_xpath,
            {"PartName": f"/{CUSTOM_PROPERTIES_XML_PATH}", "ContentType": CUSTOM_PROPERTY_CONTENT_TYPE},
        )
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def ensure_package_relationship_custom_props(rels_xml: bytes) -> bytes:
    root = ET.fromstring(rels_xml)
    rel_xpath = f"{{{PACKAGE_RELS_NS}}}Relationship"
    exists = any(
        node.get("Type") == CUSTOM_PROPERTY_REL_TYPE and node.get("Target") == "docProps/custom.xml"
        for node in root.findall(rel_xpath)
    )
    if not exists:
        existing_ids = {node.get("Id", "") for node in root.findall(rel_xpath)}
        next_id = 1
        while f"rId{next_id}" in existing_ids:
            next_id += 1
        ET.SubElement(
            root,
            rel_xpath,
            {
                "Id": f"rId{next_id}",
                "Type": CUSTOM_PROPERTY_REL_TYPE,
                "Target": "docProps/custom.xml",
            },
        )
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def write_custom_properties(output_path: str, properties: dict[str, object]) -> None:
    with zipfile.ZipFile(output_path, "r") as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}

    entries[CUSTOM_PROPERTIES_XML_PATH] = build_custom_properties_xml(properties)
    entries[CONTENT_TYPES_XML_PATH] = ensure_content_types_custom_override(entries[CONTENT_TYPES_XML_PATH])
    entries[PACKAGE_RELS_XML_PATH] = ensure_package_relationship_custom_props(entries[PACKAGE_RELS_XML_PATH])

    output_dir = os.path.dirname(output_path) or "."
    fd, temp_path = tempfile.mkstemp(suffix=".docx", dir=output_dir)
    os.close(fd)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for name, content in entries.items():
                zout.writestr(name, content)
        os.replace(temp_path, output_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
