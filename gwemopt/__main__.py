#!/usr/bin/env python

# Copyright (C) 2020 Michael Coughlin
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

""".
Gravitational-wave Electromagnetic Optimization
This script generates an optimized list of pointings and content for
reviewing gravitational-wave skymap likelihoods.
Comments should be e-mailed to michael.coughlin@ligo.org.
"""

import optparse
import os
import warnings

import astroplan
import astropy
import astropy.units as u
import numpy as np
from astropy import table, time

import gwemopt.catalog
import gwemopt.coverage
import gwemopt.efficiency
import gwemopt.footprint
import gwemopt.gracedb
import gwemopt.lightcurve
import gwemopt.mapsplit
import gwemopt.moc
import gwemopt.plotting
import gwemopt.quadrants
import gwemopt.rankedTilesGenerator
import gwemopt.segments
import gwemopt.tiles
import gwemopt.utils
import gwemopt.waw
from gwemopt.paths import DEFAULT_BASE_OUTPUT_DIR, DEFAULT_CONFIG_DIR, DEFAULT_TILING_DIR, DEFAULT_LIGHTCURVE_DIR, TESSELATION_DIR, test_skymap

if not os.getenv("DISPLAY", None):
    import matplotlib

    matplotlib.use("agg")


np.random.seed(0)

__author__ = "Michael Coughlin <michael.coughlin@ligo.org>"
__version__ = 1.0
__date__ = "6/17/2017"

# =============================================================================
#
#                               DEFINITIONS
#
# =============================================================================


def parse_commandline():
    """@Parse the options given on the command-line."""
    parser = optparse.OptionParser(usage=__doc__, version=__version__)

    parser.add_option(
        "-c", "--configDirectory", help="GW-EM config file directory.",
        default=DEFAULT_CONFIG_DIR,
    )
    parser.add_option("-s", "--skymap", help="GW skymap.", default=test_skymap)
    parser.add_option(
        "-g", "--gpstime", help="GPS time.", default=1167559936.0, type=float
    )
    parser.add_option("--do3D", action="store_true", default=False)

    parser.add_option(
        "-o", "--outputDir", help="output directory", default=DEFAULT_BASE_OUTPUT_DIR
    )
    parser.add_option("-n", "--event", help="event name", default="G268556")
    parser.add_option(
        "--tilingDir", help="tiling directory", default=DEFAULT_TILING_DIR
    )

    parser.add_option("--doEvent", action="store_true", default=False)
    parser.add_option("--doSkymap", action="store_true", default=False)
    parser.add_option("--doSamples", action="store_true", default=False)

    parser.add_option("--doCoverage", action="store_true", default=False)

    parser.add_option("--doSchedule", action="store_true", default=False)
    parser.add_option("--scheduleType", help="schedule type", default="greedy_slew")
    parser.add_option(
        "--timeallocationType", help="time allocation type", default="powerlaw"
    )

    parser.add_option("--doPlots", action="store_true", default=False)
    parser.add_option("--doDatabase", action="store_true", default=False)
    parser.add_option("--doMovie", action="store_true", default=False)
    parser.add_option("--doTiles", action="store_true", default=False)
    parser.add_option("--tilesType", help="tiling type", default="moc")
    parser.add_option("--doMindifFilt", action="store_true", default=False)

    parser.add_option("--doIterativeTiling", action="store_true", default=False)
    parser.add_option("--doMinimalTiling", action="store_true", default=False)
    parser.add_option("--doOverlappingScheduling", action="store_true", default=False)
    parser.add_option("--doPerturbativeTiling", action="store_true", default=False)
    parser.add_option("--doOrderByObservability", action="store_true", default=False)

    parser.add_option("--doCatalog", action="store_true", default=False)
    parser.add_option("--doUseCatalog", action="store_true", default=False)
    parser.add_option("--doCatalogDatabase", action="store_true", default=False)
    parser.add_option("--catalogDir", help="catalog directory", default="../catalogs")
    parser.add_option("--galaxy_catalog", help="Source catalog", default="GLADE")
    parser.add_option(
        "--galaxy_grade",
        help="grade to use ('S', 'Sloc' or 'Smass')",
        type=str,
        default="S",
    )
    parser.add_option("--writeCatalog", action="store_true", default=False)
    parser.add_option("--catalog_n", default=1.0, type=float)
    parser.add_option("--AGN_flag", action="store_true", default=False)
    parser.add_option("--doObservability", action="store_true", default=False)
    parser.add_option("--doObservabilityExit", action="store_true", default=False)
    parser.add_option("--observability_thresh", default=0.05, type=float)
    parser.add_option("--doSkybrightness", action="store_true", default=False)

    parser.add_option("--doEfficiency", action="store_true", default=False)
    parser.add_option(
        "-e",
        "--efficiencyOutput",
        help="Output file of the efficiency.",
        default="efficiency.txt",
    )
    parser.add_option(
        "-m", "--modelType", help="(file, Bulla, Tophat, afterglow)", default="Tophat"
    )
    parser.add_option("--mag", help="mag.", default=-16, type=float)
    parser.add_option("--dmag", help="dmag.", default=0.0, type=float)
    parser.add_option("-t", "--telescopes", help="Telescope names.", default="ATLAS")
    parser.add_option(
        "-d",
        "--coverageFiles",
        help="Telescope coverage files.",
        default="../data/ATLAS_GW170104.dat",
    )
    parser.add_option(
        "-l",
        "--lightcurveFiles",
        help="Lightcurve files.",
        default=DEFAULT_LIGHTCURVE_DIR.joinpath("Me2017_H4M050V20.dat"),
    )
    parser.add_option(
        "--observedTiles", help="Tiles that have already been observed.", default=""
    )
    parser.add_option("--Ninj", default=10000, type=int)
    parser.add_option("--Ntiles", default=10, type=int)
    parser.add_option("--doCalcTiles", action="store_true", default=False)
    parser.add_option("--Ntiles_cr", default=0.70, type=float)
    parser.add_option("--Ndet", default=1, type=int)
    parser.add_option("--nside", default=256, type=int)
    parser.add_option("--DScale", default=1.0, type=float)
    parser.add_option("--Tobs", default="0.0,1.0")

    parser.add_option("--mindiff", default=0.0, type=float)

    parser.add_option("--powerlaw_cl", default=0.9, type=float)
    parser.add_option("--powerlaw_n", default=1.0, type=float)
    parser.add_option("--powerlaw_dist_exp", default=0, type=float)

    parser.add_option("--galaxies_FoV_sep", default=1.0, type=float)

    parser.add_option("--doFootprint", action="store_true", default=False)
    parser.add_option("--footprint_ra", default=30.0, type=float)
    parser.add_option("--footprint_dec", default=60.0, type=float)
    parser.add_option("--footprint_radius", default=10.0, type=float)
    parser.add_option("--doTreasureMap", action="store_true", default=False)
    parser.add_option("--treasuremap_token", help="Treasure Map API Token.", default="")
    parser.add_option(
        "--treasuremap_status",
        help="Status of Treasure Map observations to be queried.",
        default="planned,completed",
    )
    parser.add_option("--graceid", default="S190426c")
    parser.add_option("--start_time", default=None)
    parser.add_option("--end_time", default=None)

    parser.add_option("--doTrueLocation", action="store_true", default=False)
    parser.add_option("--true_ra", default=30.0, type=float)
    parser.add_option("--true_dec", default=60.0, type=float)
    parser.add_option("--true_distance", default=100.0, type=float)

    parser.add_option("--dt", default=14.0, type=float)

    parser.add_option("-a", "--airmass", default=2.5, type=float)

    parser.add_option("--doSingleExposure", action="store_true", default=False)
    parser.add_option("--filters", default="r,g,r")
    parser.add_option("--doAlternatingFilters", action="store_true", default=False)
    parser.add_option("--doRASlices", action="store_true", default=False)
    parser.add_option("--nside_down", default=2, type=int)
    parser.add_option("--max_filter_sets", default=4, type=int)
    parser.add_option("--iterativeOverlap", default=0.0, type=float)
    parser.add_option("--maximumOverlap", default=1.0, type=float)
    parser.add_option("--doBalanceExposure", action="store_true", default=False)

    parser.add_option("--exposuretimes", default="30.0,30.0,30.0")

    parser.add_option("--doMaxTiles", action="store_true", default=False)
    parser.add_option("--max_nb_tiles", default="-1,-1,-1")
    parser.add_option("--doReferences", action="store_true", default=False)

    parser.add_option("--doChipGaps", action="store_true", default=False)
    parser.add_option("--doUsePrimary", action="store_true", default=False)
    parser.add_option("--doUseSecondary", action="store_true", default=False)

    parser.add_option("--doSplit", action="store_true", default=False)
    parser.add_option("--splitType", default="regional")
    parser.add_option("--Nregions", default=768, type=int)

    parser.add_option("--doParallel", action="store_true", default=False)
    parser.add_option("--Ncores", default=4, type=int)

    parser.add_option("--doBlocks", action="store_true", default=False)
    parser.add_option("--Nblocks", default=4, type=int)

    parser.add_option("--doRASlice", action="store_true", default=False)
    parser.add_option("--raslice", default="0.0,24.0")
    parser.add_option("--program_id", default=-1, type=int)

    parser.add_option("--absmag", default=-15.0, type=float)

    parser.add_option("--doRotate", action="store_true", default=False)
    parser.add_option("--theta", help="theta rotation.", default=0.0, type=float)
    parser.add_option("--phi", help="phi rotation.", default=0.0, type=float)

    parser.add_option("--doAvoidGalacticPlane", action="store_true", default=False)
    parser.add_option(
        "--galactic_limit", help="Galactic limit.", default=15.0, type=float
    )

    parser.add_option(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Run verbosely. (Default: False)",
    )

    opts, args = parser.parse_args()

    return opts


def params_struct(opts):
    """@Creates gwemopt params structure
    @param opts
        gwemopt command line options
    """

    telescopes = opts.telescopes.split(",")

    params = {}
    params["config"] = {}
    for telescope in telescopes:
        configFile = DEFAULT_CONFIG_DIR.joinpath(telescope + ".config")
        params["config"][telescope] = gwemopt.utils.readParamsFromFile(configFile)
        params["config"][telescope]["telescope"] = telescope
        if opts.doSingleExposure:
            exposuretime = np.array(opts.exposuretimes.split(","), dtype=float)[0]

            params["config"][telescope]["magnitude_orig"] = params["config"][telescope][
                "magnitude"
            ]
            params["config"][telescope]["exposuretime_orig"] = params["config"][
                telescope
            ]["exposuretime"]

            nmag = -2.5 * np.log10(
                np.sqrt(params["config"][telescope]["exposuretime"] / exposuretime)
            )
            params["config"][telescope]["magnitude"] = (
                params["config"][telescope]["magnitude"] + nmag
            )
            params["config"][telescope]["exposuretime"] = exposuretime
        if "tesselationFile" in params["config"][telescope]:
            tessfile = TESSELATION_DIR.joinpath(
                params["config"][telescope]["tesselationFile"]
            )
            if not os.path.isfile(tessfile):
                if params["config"][telescope]["FOV_type"] == "circle":
                    gwemopt.tiles.tesselation_spiral(params["config"][telescope])
                elif params["config"][telescope]["FOV_type"] == "square":
                    gwemopt.tiles.tesselation_packing(params["config"][telescope])
            if opts.tilesType == "galaxy":
                params["config"][telescope]["tesselation"] = np.empty((3,))
            else:

                params["config"][telescope]["tesselation"] = np.loadtxt(
                    tessfile, usecols=(0, 1, 2), comments="%"
                )

        if "referenceFile" in params["config"][telescope]:
            reffile = os.path.join(
                opts.configDirectory, params["config"][telescope]["referenceFile"]
            )
            refs = table.unique(
                table.Table.read(reffile, format="ascii", data_start=2, data_end=-1)[
                    "field", "fid"
                ]
            )
            reference_images = {
                group[0]["field"]: group["fid"].astype(int).tolist()
                for group in refs.group_by("field").groups
            }
            reference_images_map = {1: "g", 2: "r", 3: "i"}
            for key in reference_images:
                reference_images[key] = [
                    reference_images_map.get(n, n) for n in reference_images[key]
                ]
            params["config"][telescope]["reference_images"] = reference_images

        location = astropy.coordinates.EarthLocation(
            params["config"][telescope]["longitude"],
            params["config"][telescope]["latitude"],
            params["config"][telescope]["elevation"],
        )
        observer = astroplan.Observer(location=location)
        params["config"][telescope]["observer"] = observer

        # observer = ephem.Observer()
        # observer.lat = str(params["config"][telescope]["latitude"])
        # observer.lon = str(params["config"][telescope]["longitude"])
        # observer.horizon = str(-12.0)
        # observer.elevation = params["config"][telescope]["elevation"]
        # params["config"][telescope]["observer"] = observer

    params["mag"] = opts.mag
    params["dmag"] = opts.dmag
    params["modelType"] = opts.modelType
    params["skymap"] = opts.skymap
    params["gpstime"] = opts.gpstime
    params["outputDir"] = opts.outputDir
    params["tilingDir"] = opts.tilingDir
    params["catalogDir"] = opts.catalogDir
    params["event"] = opts.event
    params["coverageFiles"] = opts.coverageFiles.split(",")
    params["telescopes"] = telescopes
    params["lightcurveFiles"] = str(opts.lightcurveFiles).split(",")
    params["tilesType"] = opts.tilesType
    params["scheduleType"] = opts.scheduleType
    params["timeallocationType"] = opts.timeallocationType
    params["Ninj"] = opts.Ninj
    params["Ndet"] = opts.Ndet
    params["Ntiles"] = opts.Ntiles
    params["Ntiles_cr"] = opts.Ntiles_cr
    params["DScale"] = opts.DScale
    params["nside"] = opts.nside
    params["Tobs"] = np.array(opts.Tobs.split(","), dtype=float)
    params["powerlaw_cl"] = opts.powerlaw_cl
    params["powerlaw_n"] = opts.powerlaw_n
    params["powerlaw_dist_exp"] = opts.powerlaw_dist_exp
    params["galaxies_FoV_sep"] = opts.galaxies_FoV_sep
    params["observedTiles"] = opts.observedTiles.split(",")
    params["doPlots"] = opts.doPlots
    params["doMovie"] = opts.doMovie
    params["doMindifFilt"] = opts.doMindifFilt
    params["doObservability"] = opts.doObservability
    params["do3D"] = opts.do3D
    params["doDatabase"] = opts.doDatabase
    params["doTreasureMap"] = opts.doTreasureMap
    params["treasuremap_token"] = opts.treasuremap_token
    params["treasuremap_status"] = opts.treasuremap_status.split(",")
    params["graceid"] = opts.graceid
    params["program_id"] = opts.program_id
    params["doCalcTiles"] = opts.doCalcTiles
    params["doFootprint"] = opts.doFootprint
    params["footprint_ra"] = opts.footprint_ra
    params["footprint_dec"] = opts.footprint_dec
    params["footprint_radius"] = opts.footprint_radius

    params["doRASlice"] = opts.doRASlice
    params["raslice"] = np.array(opts.raslice.split(","), dtype=float)

    params["dt"] = opts.dt

    params["galaxy_catalog"] = opts.galaxy_catalog

    params["doSingleExposure"] = opts.doSingleExposure
    params["doBalanceExposure"] = opts.doBalanceExposure
    params["unbalanced_tiles"] = None
    params["filters"] = opts.filters.split(",")
    params["exposuretimes"] = np.array(opts.exposuretimes.split(","), dtype=float)
    params["doMovie_supersched"] = False
    params["doSuperSched"] = False
    params["doUpdateScheduler"] = False
    params["doMaxTiles"] = opts.doMaxTiles
    params["max_nb_tiles"] = np.array(opts.max_nb_tiles.split(","), dtype=float)
    params["mindiff"] = opts.mindiff
    params["doAlternatingFilters"] = opts.doAlternatingFilters
    params["doReferences"] = opts.doReferences

    params["airmass"] = opts.airmass

    params["doIterativeTiling"] = opts.doIterativeTiling
    params["iterativeOverlap"] = opts.iterativeOverlap
    params["maximumOverlap"] = opts.maximumOverlap
    params["doMinimalTiling"] = opts.doMinimalTiling
    params["doOverlappingScheduling"] = opts.doOverlappingScheduling
    params["doPerturbativeTiling"] = opts.doPerturbativeTiling
    params["doOrderByObservability"] = opts.doOrderByObservability
    params["doRASlices"] = opts.doRASlices
    params["max_filter_sets"] = opts.max_filter_sets
    params["nside_down"] = opts.nside_down

    params["doCatalog"] = opts.doCatalog
    params["catalog_n"] = opts.catalog_n
    params["doUseCatalog"] = opts.doUseCatalog
    params["doCatalogDatabase"] = opts.doCatalogDatabase
    params["galaxy_grade"] = opts.galaxy_grade
    params["writeCatalog"] = opts.writeCatalog
    params["AGN_flag"] = opts.AGN_flag

    params["doChipGaps"] = opts.doChipGaps
    params["doUsePrimary"] = opts.doUsePrimary
    params["doUseSecondary"] = opts.doUseSecondary

    params["doSplit"] = opts.doSplit
    params["splitType"] = opts.splitType
    params["Nregions"] = opts.Nregions

    params["doParallel"] = opts.doParallel
    params["Ncores"] = opts.Ncores

    params["doBlocks"] = opts.doBlocks
    params["Nblocks"] = opts.Nblocks

    params["absmag"] = opts.absmag

    params["doRotate"] = opts.doRotate
    params["phi"] = opts.phi
    params["theta"] = opts.theta

    params["doTrueLocation"] = opts.doTrueLocation
    params["true_ra"] = opts.true_ra
    params["true_dec"] = opts.true_dec
    params["true_distance"] = opts.true_distance

    params["doAvoidGalacticPlane"] = opts.doAvoidGalacticPlane
    params["galactic_limit"] = opts.galactic_limit

    if opts.start_time is None:
        params["start_time"] = time.Time.now() - time.TimeDelta(1.0 * u.day)
    else:
        params["start_time"] = time.Time(opts.start_time, format="isot", scale="utc")

    if opts.end_time is None:
        params["end_time"] = time.Time.now()
    else:
        params["end_time"] = time.Time(opts.end_time, format="isot", scale="utc")

    return params


# =============================================================================
#
#                                    MAIN
#
# =============================================================================

warnings.filterwarnings("ignore")

# Parse command line
opts = parse_commandline()
if not os.path.isdir(opts.outputDir):
    os.makedirs(opts.outputDir)

params = params_struct(opts)

if len(params["filters"]) != len(params["exposuretimes"]):
    print("The number of filters specified must match the number of exposure times.")
    exit(0)

if opts.doEvent:
    params["skymap"], eventinfo = gwemopt.gracedb.get_event(params)
    params["gpstime"] = eventinfo["gpstime"]
elif opts.doFootprint:
    params["skymap"] = gwemopt.footprint.get_skymap(params)
elif opts.doSkymap:
    pass
else:
    print("Need to enable --doEvent, --doFootprint or --doSkymap")
    exit(0)

params = gwemopt.segments.get_telescope_segments(params)

print("Loading skymap...")
# Function to read maps
if opts.do3D:
    map_struct = gwemopt.utils.read_skymap(params, is3D=True)
else:
    map_struct = gwemopt.utils.read_skymap(params, is3D=False)

if opts.doCatalog:
    print("Generating catalog...")
    map_struct, catalog_struct = gwemopt.catalog.get_catalog(params, map_struct)

if opts.doPlots:
    print("Plotting skymap...")
    gwemopt.plotting.skymap(params, map_struct)

if opts.doObservability:
    print("Generating observability")
    observability_struct = gwemopt.utils.observability(params, map_struct)
    map_struct["observability"] = observability_struct
    if opts.doPlots:
        print("Plotting observability...")
        gwemopt.plotting.observability(params, map_struct)
    if opts.doObservabilityExit:
        for telescope in params["telescopes"]:
            if (
                np.sum(observability_struct[telescope]["prob"])
                < opts.observability_thresh
            ):
                print(
                    "Observability for %s: %.5f < %.5f... exiting."
                    % (
                        telescope,
                        np.sum(observability_struct[telescope]["prob"]),
                        opts.observability_thresh,
                    )
                )

                if params["doTrueLocation"]:
                    lightcurve_structs = gwemopt.lightcurve.read_files(
                        params["lightcurveFiles"]
                    )
                    for key in lightcurve_structs.keys():
                        filename = os.path.join(
                            params["outputDir"],
                            "efficiency_true_"
                            + lightcurve_structs[key]["name"]
                            + ".txt",
                        )
                        fid = open(filename, "w")
                        fid.write("0")
                        fid.close()
                exit(0)

if opts.doSamples:
    print("Generating samples from skymap...")
    if opts.do3D:
        samples_struct = gwemopt.utils.samples_from_skymap(map_struct, is3D=True)
    else:
        samples_struct = gwemopt.utils.samples_from_skymap(map_struct, is3D=False)


if opts.doSplit:
    print("Splitting skymap...")
    map_struct["groups"] = gwemopt.mapsplit.similar_range(params, map_struct)

if opts.doTiles:
    if params["tilesType"] == "moc":
        print("Generating MOC struct...")
        moc_structs = gwemopt.moc.create_moc(params, map_struct=map_struct)
        tile_structs = gwemopt.tiles.moc(params, map_struct, moc_structs)
    elif params["tilesType"] == "ranked":
        print("Generating ranked struct...")
        # tile_structs = gwemopt.tiles.rankedTiles(params, map_struct)
        moc_structs = gwemopt.rankedTilesGenerator.create_ranked(params, map_struct)
        tile_structs = gwemopt.tiles.moc(params, map_struct, moc_structs)
    elif params["tilesType"] == "hierarchical":
        print("Generating hierarchical struct...")
        tile_structs = gwemopt.tiles.hierarchical(params, map_struct)
        params["Ntiles"] = []
        for telescope in params["telescopes"]:
            params["config"][telescope]["tesselation"] = np.empty((0, 3))
            tiles_struct = tile_structs[telescope]
            for index in tiles_struct.keys():
                ra, dec = tiles_struct[index]["ra"], tiles_struct[index]["dec"]
                params["config"][telescope]["tesselation"] = np.append(
                    params["config"][telescope]["tesselation"],
                    [[index, ra, dec]],
                    axis=0,
                )
            params["Ntiles"].append(len(tiles_struct.keys()))

    elif params["tilesType"] == "greedy":
        print("Generating greedy struct...")
        tile_structs = gwemopt.tiles.greedy(params, map_struct)
        for telescope in params["telescopes"]:
            params["config"][telescope]["tesselation"] = np.empty((0, 3))
            tiles_struct = tile_structs[telescope]
            for index in tiles_struct.keys():
                ra, dec = tiles_struct[index]["ra"], tiles_struct[index]["dec"]
                params["config"][telescope]["tesselation"] = np.append(
                    params["config"][telescope]["tesselation"],
                    [[index, ra, dec]],
                    axis=0,
                )

    elif params["tilesType"] == "galaxy":
        print("Generating galaxy struct...")
        tile_structs = gwemopt.tiles.galaxy(params, map_struct, catalog_struct)
        for telescope in params["telescopes"]:
            params["config"][telescope]["tesselation"] = np.empty((0, 3))
            tiles_struct = tile_structs[telescope]
            for index in tiles_struct.keys():
                ra, dec = tiles_struct[index]["ra"], tiles_struct[index]["dec"]
                params["config"][telescope]["tesselation"] = np.append(
                    params["config"][telescope]["tesselation"],
                    [[index, ra, dec]],
                    axis=0,
                )
    else:
        print("Need tilesType to be moc, greedy, hierarchical, ranked or galaxy")
        exit(0)

    if opts.doPlots:
        print("Plotting tiles struct...")
        gwemopt.plotting.tiles(params, map_struct, tile_structs)


if opts.doSchedule:
    if opts.doTiles:
        print("Generating coverage...")
        tile_structs, coverage_struct = gwemopt.coverage.timeallocation(
            params, map_struct, tile_structs
        )
    else:
        print("Need to enable --doTiles to use --doSchedule")
        exit(0)
elif opts.doCoverage:
    print("Reading coverage from file...")
    coverage_struct = gwemopt.coverage.read_coverage_files(
        params, moc_structs=moc_structs
    )

if opts.doSchedule or opts.doCoverage:
    print("Summary of coverage...")
    if opts.doCatalog:
        gwemopt.scheduler.summary(
            params, map_struct, coverage_struct, catalog_struct=catalog_struct
        )
    else:
        gwemopt.scheduler.summary(params, map_struct, coverage_struct)

    if opts.doPlots:
        print("Plotting coverage...")
        if opts.doCatalog:
            gwemopt.plotting.coverage(
                params, map_struct, coverage_struct, catalog_struct=catalog_struct
            )
        else:
            gwemopt.plotting.coverage(params, map_struct, coverage_struct)

if opts.doEfficiency:
    if opts.doSchedule or opts.doCoverage:
        print("Computing efficiency...")
        if opts.modelType == "file":
            lightcurve_structs = gwemopt.lightcurve.read_files(
                params["lightcurveFiles"]
            )
        elif opts.modelType == "Tophat":
            lightcurve_structs = gwemopt.lightcurve.tophat(
                mag0=opts.mag, dmag=opts.dmag
            )
        efficiency_structs = {}
        for key in lightcurve_structs.keys():
            lightcurve_struct = lightcurve_structs[key]
            efficiency_struct = gwemopt.efficiency.compute_efficiency(
                params, map_struct, lightcurve_struct, coverage_struct, do3D=opts.do3D
            )
            efficiency_structs[key] = efficiency_struct
            efficiency_structs[key]["legend_label"] = lightcurve_struct["legend_label"]
            if opts.do3D:
                print(
                    f'Percent detections out of {params["Ninj"]} injected KNe: {efficiency_structs[key]["3D"]*100}% '
                )

        if opts.doPlots:
            print("Plotting efficiency...")
            gwemopt.plotting.efficiency(params, map_struct, efficiency_structs)
    else:
        print("Need to enable --doSchedule or --doCoverage for --doEfficiency")
        exit(0)
