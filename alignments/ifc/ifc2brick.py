from brickschema import Graph
import ifcopenshell
import ifcopenshell.util.element as Element
from brickschema.namespaces import BRICK, A
from rdflib import URIRef, Namespace, RDFS, Literal
import urllib.parse
import argparse
from pyshacl import validate

# Conversion of IFC types to Brick Types
# The IFC types only go into real detail about the Architectural assets
def ifc_type_2_brick_arch(element):
    ifc_type = element.get_info()["type"]
    type = None
    if ifc_type == "IfcWall":
        type = BRICK.Wall
    elif ifc_type == "IfcDoor":
        type = BRICK.Door
    elif ifc_type == "IfcRailing":
        type = BRICK.Railing
    elif ifc_type == "IfcColumn":
        type = BRICK.Column
    elif ifc_type == "IfcSlab":
        type = BRICK.Slab
    elif ifc_type == "IfcWallStandardCase":
        type = BRICK.Wall
    elif ifc_type == "IfcBeam":
        type = BRICK.Beam
    elif ifc_type == "IfcStair":
        type = BRICK.Stair
    elif ifc_type == "IfcWindow":
        type = BRICK.Window
    elif ifc_type == "IfcStairFlight":
        type = BRICK.StairFlight
    elif ifc_type == "IfcRoof":
        type = BRICK.Roof
    else:
        type = BRICK.Equipment
    return type


# Add Dimensions Pset to the element
def add_dimensions_to_element(BLDG, g, uri, element):
    if "Dimensions" in Element.get_psets(element, psets_only=True).keys():
        dimensions = Element.get_psets(element, psets_only=True)["Dimensions"]
        if "Area" in dimensions.keys():

            g.add((BLDG[uri], BRICK.grossArea, Literal(round(dimensions["Area"], 2))))
        if "Length" in dimensions.keys():
            g.add((BLDG[uri], BRICK.length, Literal(round(dimensions["Length"], 2))))
        if "Volume" in dimensions.keys():
            g.add((BLDG[uri], BRICK.volume, Literal(round(dimensions["Volume"], 2))))


# Adds Identity Data Pset to the element
def add_identity_data_to_element(BLDG, g, uri, element):
    if "Identity Data" in Element.get_psets(element, psets_only=True).keys():
        data = Element.get_psets(element, psets_only=True)["Identity Data"]
        if "Model" in data.keys():
            g.add(
                (
                    BLDG[uri],
                    BRICK.modelNo,
                    Literal(data["Model"]),
                )
            )
        if "Manufacturer" in data.keys():
            g.add(
                (
                    BLDG[uri],
                    BRICK.manufacturer,
                    Literal(data["Manufacturer"]),
                )
            )
        if "Type Name" in data.keys():
            g.add(
                (
                    BLDG[uri],
                    BRICK.typeName,
                    Literal(data["Type Name"]),
                )
            )


# Create a brick element from a IFC element
# Get its brick type
# Add Name and external id
# Add the dimensions and identity data
def create_element(BLDG, g, element_uri, element):
    brick_type = ifc_type_2_brick_arch(element)
    g.add((BLDG[element_uri], A, brick_type))
    g.add(
        (
            BLDG[element_uri],
            RDFS.label,
            Literal(element.Name.replace('"', "").replace("'", "")),
        )
    )
    g.add(
        (
            BLDG[element_uri],
            BRICK.externalId,
            Literal(element.GlobalId),
        )
    )
    add_dimensions_to_element(BLDG, g, element_uri, element)
    add_identity_data_to_element(BLDG, g, element_uri, element)


def load_ifc_file(ifc_file_path):

    ifc = ifcopenshell.open(ifc_file_path)
    project = ifc.by_type("IfcProject")[0]
    site = project.IsDecomposedBy[0].RelatedObjects[0]
    building = site.IsDecomposedBy[0].RelatedObjects[0]
    return project, site, building, ifc


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc", help="path to architectural ifc file")
    parser.add_argument("--buildingUri")
    parser.add_argument("--buildingName")
    parser.add_argument("--out", help="Outfile .ttl file path")

    args = parser.parse_args()
    assert args.ifc
    assert args.buildingUri
    assert args.buildingName

    # Load IFC file objects
    project, site, building, ifc = load_ifc_file(args.ifc)

    g = Graph()
    BLDG = Namespace("syyclops.com:setty_us#")

    # Create a Building
    building_uri = args.buildingUri
    g.add((BLDG[building_uri], A, BRICK.Building))
    g.add((BLDG[building_uri], RDFS.label, Literal(args.buildingName)))
    # Building location
    g.add((BLDG[building_uri], BRICK.latitude, Literal(site.RefLatitude)))
    g.add((BLDG[building_uri], BRICK.Longitude, Literal(site.RefLongitude)))
    g.add(
        (
            BLDG[building_uri],
            BRICK.elevation,
            Literal(site.RefElevation),
        )
    )

    # Create the Floors of the Building
    stories = building.IsDecomposedBy[0].RelatedObjects
    for story in stories:
        story_uri = story.Name.replace(" ", "_")
        g.add((BLDG[story_uri], A, BRICK.Floor))
        g.add((BLDG[story_uri], BRICK.hasLocation, BLDG[building_uri]))
        g.add((BLDG[story_uri], RDFS.label, Literal(story.Name)))

        # Create the rooms
        if story.IsDecomposedBy:
            rooms = story.IsDecomposedBy[0].RelatedObjects
            for room in rooms:
                room_name = room.LongName + " " + room.Name
                room_uri = room.GlobalId
                g.add((BLDG[room_uri], A, BRICK.Room))
                g.add((BLDG[room_uri], BRICK.hasLocation, BLDG[story_uri]))
                g.add((BLDG[room_uri], RDFS.label, Literal(room_name)))
                add_dimensions_to_element(BLDG, g, room_uri, room)
                g.add(
                    (
                        BLDG[room_uri],
                        BRICK.externalId,
                        Literal(room.GlobalId),
                    )
                )

                # Create assets inside a room
                if room.ContainsElements:
                    elements_in_room = room.ContainsElements[0].RelatedElements
                    for element in elements_in_room:
                        element_uri = element.GlobalId

                        create_element(BLDG, g, element_uri, element)
                        g.add((BLDG[element_uri], BRICK.hasLocation, BLDG[room_uri]))

        # Create Assets that are apart of the Floors
        if story.ContainsElements:
            elements_on_floor = story.ContainsElements[0].RelatedElements
            for element in elements_on_floor:
                element_uri = element.GlobalId

                create_element(BLDG, g, element_uri, element)
                g.add((BLDG[element_uri], BRICK.hasLocation, BLDG[story_uri]))

    # Create Systems
    # First create the system node then assign all elements that make up the system
    systems = ifc.by_type("IfcSystem")
    if systems:
        for system in systems:
            system_uri = system.GlobalId
            g.add((BLDG[system_uri], A, BRICK.System))
            g.add((BLDG[system_uri], RDFS.label, Literal(system.ObjectType)))
            g.add(
                (
                    BLDG[system_uri],
                    BRICK.externalId,
                    Literal(system.GlobalId),
                )
            )

            for element in system.IsGroupedBy[0].RelatedObjects:
                element_uri = element.GlobalId
                g.add((BLDG[element_uri], BRICK.isPartOf, BLDG[system_uri]))

    valid, _, report = validate(g)
    print(f"Graph is valid? {valid}")
    print(report)
    if args.out:
        g.serialize(args.out, format="turtle")
