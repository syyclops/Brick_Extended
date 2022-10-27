from brickschema import Graph
import ifcopenshell
import ifcopenshell.util.element as Element
from brickschema.namespaces import BRICK, A
from rdflib import URIRef, Namespace, RDFS, Literal
import urllib.parse
import argparse
from pyshacl import validate

REC = Namespace("https://w3id.org/rec#")


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
                    URIRef("https://brickschema.org/schema/Brick#modelNo"),
                    Literal(data["Model"]),
                )
            )
        if "Manufacturer" in data.keys():
            g.add(
                (
                    BLDG[uri],
                    URIRef("https://brickschema.org/schema/Brick#manufacturer"),
                    Literal(data["Manufacturer"]),
                )
            )
        if "Type Name" in data.keys():
            g.add(
                (
                    BLDG[uri],
                    URIRef("https://brickschema.org/schema/Brick#typeName"),
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
            URIRef("https://brickschema.org/schema/Brick#externalId"),
            Literal(element.GlobalId),
        )
    )
    add_dimensions_to_element(BLDG, g, element_uri, element)
    add_identity_data_to_element(BLDG, g, element_uri, element)


def load_ifc_files(ifc_file_paths):
    models = {}
    for ifc_file_path in ifc_file_paths:
        ifc = ifcopenshell.open(ifc_file_path)
        project = ifc.by_type("IfcProject")[0]
        site = project.IsDecomposedBy[0].RelatedObjects[0]
        building = site.IsDecomposedBy[0].RelatedObjects[0]
        models[ifc_file_path.split("/")[-1].split(".")[0]] = {
            "site": site,
            "building": building,
            "ifc": ifc,
        }

    return models


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archModel", help="path to architectural ifc model")
    parser.add_argument("--mechModel", help="path to mechanical ifc model")
    parser.add_argument("--elecModel", help="path to electrical ifc model")
    parser.add_argument("--plumModel", help="path to plumbing ifc model")

    args = parser.parse_args()
    # Load IFC and Graph
    # ifc = ifcopenshell.open(args.archModel)
    # project = ifc.by_type("IfcProject")[0]
    # site = project.IsDecomposedBy[0].RelatedObjects[0]
    # building = site.IsDecomposedBy[0].RelatedObjects[0]

    file_paths = []
    if args.archModel:
        file_paths.append(args.archModel)
    if args.mechModel:
        file_paths.append(args.mechModel)
    if args.elecModel:
        file_paths.append(args.elecModel)
    if args.plumModel:
        file_paths.append(args.plumModel)
    assert len(file_paths) > 0
    models = load_ifc_files(file_paths)
    archSite = models["Architectural"]["site"]
    archBuilding = models["Architectural"]["building"]

    longitude = archSite.RefLongitude
    latitude = archSite.RefLatitude
    elevation = archSite.RefElevation

    g = Graph()

    rec_shacl_graph = Graph().parse(
        "https://raw.githubusercontent.com/RealEstateCore/rec/main/Ontology/SHACL/RealEstateCore/rec.ttl",
        format="ttl",
    )

    g.bind("rec", REC)
    BLDG = Namespace("syyclops.com:setty_us#")
    # bldg_graph = g.graph(URIRef(BLDG))

    # Create a Building
    building_uri = "building_1"
    g.add((BLDG[building_uri], A, BRICK.Building))
    g.add((BLDG[building_uri], RDFS.label, Literal("Setty US")))
    # Building location
    g.add((BLDG[building_uri], REC.anthony, Literal(latitude)))
    g.add((BLDG[building_uri], REC.Longitude, Literal(longitude)))
    g.add(
        (
            BLDG[building_uri],
            URIRef("https://brickschema.org/schema/Brick#elevation"),
            Literal(elevation),
        )
    )

    # Create the Floors of the Building
    for key in models:
        print(key)
        stories = models[key]["building"].IsDecomposedBy[0].RelatedObjects
        for story in stories:
            story_uri = story.Name.replace(" ", "_")
            g.add((BLDG[story_uri], A, BRICK.Floor))
            g.add((BLDG[story_uri], BRICK.hasLocation, BLDG[building_uri]))
            g.add((BLDG[story_uri], RDFS.label, Literal(story.Name)))

            # Create the rooms and the assets within them
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
                            URIRef("https://brickschema.org/schema/Brick#externalId"),
                            Literal(room.GlobalId),
                        )
                    )

                    if room.ContainsElements:
                        elements_in_room = room.ContainsElements[0].RelatedElements
                        for element in elements_in_room:
                            element_uri = element.GlobalId

                            create_element(BLDG, g, element_uri, element)
                            g.add(
                                (BLDG[element_uri], BRICK.hasLocation, BLDG[room_uri])
                            )

            # Create Assets that are apart of the Floors
            if story.ContainsElements:
                elements_on_floor = story.ContainsElements[0].RelatedElements
                for element in elements_on_floor:
                    element_uri = element.GlobalId

                    create_element(BLDG, g, element_uri, element)
                    g.add((BLDG[element_uri], BRICK.hasLocation, BLDG[story_uri]))

        # Create Systems
        # First create the system node then assign all elements that make up the system
        systems = models[key]["ifc"].by_type("IfcSystem")
        if systems:
            for system in systems:
                system_uri = system.GlobalId
                g.add((BLDG[system_uri], A, BRICK.System))
                g.add((BLDG[system_uri], RDFS.label, Literal(system.ObjectType)))
                g.add(
                    (
                        BLDG[system_uri],
                        URIRef("https://brickschema.org/schema/Brick#externalId"),
                        Literal(system.GlobalId),
                    )
                )

                for element in system.IsGroupedBy[0].RelatedObjects:
                    element_uri = element.GlobalId
                    g.add((BLDG[element_uri], BRICK.isPartOf, BLDG[system_uri]))

    # bld_graph = g.graph(URIRef(BLDG))
    valid, _, report = validate(g, shacl_graph=rec_shacl_graph)
    print(f"Graph is valid? {valid}")
    print(report)
    if not valid:
        print(report)
    g.serialize("test2.ttl", format="turtle")
