"""The main function."""

import argparse
import os
import shutil
import sys
from operator import attrgetter
from unicodedata import normalize

from mosfit import __version__
from mosfit.fitter import Fitter
from mosfit.printer import Printer
from mosfit.utils import get_mosfit_hash, is_master


class SortingHelpFormatter(argparse.HelpFormatter):
    """Sort argparse arguments by argument name."""

    def add_arguments(self, actions):
        """Add sorting action based on `option_strings`."""
        actions = sorted(actions, key=attrgetter('option_strings'))
        super(SortingHelpFormatter, self).add_arguments(actions)


def get_parser():
    """Retrieve MOSFiT's `argparse.ArgumentParser` object."""
    parser = argparse.ArgumentParser(
        prog='MOSFiT',
        description='Fit astrophysical light curves using AstroCats data.',
        formatter_class=SortingHelpFormatter)

    parser.add_argument(
        '--events',
        '-e',
        dest='events',
        default=[''],
        nargs='+',
        help=("List of event names to be fit, delimited by spaces. If an "
              "event name contains a space, enclose the event's name in "
              "double quote marks, e.g. \"SDSS-II SN 5944\"."))

    parser.add_argument(
        '--models',
        '-m',
        dest='models',
        default=['default'],
        nargs='+',
        help=("List of models to use to fit against the listed events. The "
              "model can either be a name of a model included with MOSFiT, or "
              "a path to a custom model JSON file generated by the user."))

    parser.add_argument(
        '--parameter-paths',
        '-P',
        dest='parameter_paths',
        default=[''],
        nargs='+',
        help=("Paths to parameter files corresponding to each model file; "
              "length of this list should be equal to the length of the list "
              "of models"))

    parser.add_argument(
        '--plot-points',
        dest='plot_points',
        default=100,
        help=("Set the number of plot points when producing light curves from "
              "models without fitting against any actual transient data."))

    parser.add_argument(
        '--max-time',
        dest='max_time',
        type=float,
        default=1000.,
        help=("Set the maximum time for model light curves to be plotted "
              "until."))

    parser.add_argument(
        '--band-list',
        '--extra-bands',
        dest='band_list',
        default=[],
        nargs='+',
        help=("List of additional bands to plot when plotting model light "
              "curves that are not being matched to actual transient data."))

    parser.add_argument(
        '--band-systems',
        '--extra-systems',
        dest='band_systems',
        default=[],
        nargs='+',
        help=("List of photometric systems corresponding to the bands listed "
              "in `--band-list`."))

    parser.add_argument(
        '--band-instruments',
        '--extra-instruments',
        dest='band_instruments',
        default=[],
        nargs='+',
        help=("List of instruments corresponding to the bands listed "
              "in `--band-list`."))

    parser.add_argument(
        '--band-bandsets',
        '--extra-bandsets',
        dest='band_bandsets',
        default=[],
        nargs='+',
        help=("List of bandsets corresponding to the bands listed "
              "in `--band-list`."))

    parser.add_argument(
        '--exclude-bands',
        dest='exclude_bands',
        default=[],
        nargs='+',
        help=("List of bands to exclude in fitting."))

    parser.add_argument(
        '--exclude-instruments',
        dest='exclude_instruments',
        default=[],
        nargs='+',
        help=("List of instruments to exclude in fitting corresponding to "
              "the bands listed in `--exclude-bands`."))

    parser.add_argument(
        '--fix-parameters',
        '-F',
        dest='user_fixed_parameters',
        default=[],
        nargs='+',
        help=("Pairs of parameter names and values to fix for the current "
              "fit. Example: `-F kappa 1.0 vejecta 1.0e4` would fix the "
              "`kappa` and `vejecta` parameters to those values. If the "
              "second value is recognized to be an existing key, the whole "
              "list will be assumed to just be a list of keys and the "
              "default values specified in the model JSON files will be "
              "used. If the name is a parameter class (e.g. `covariance`), "
              "all variables of that class will be fixed."))

    parser.add_argument(
        '--iterations',
        '-i',
        dest='iterations',
        type=int,
        default=-1,
        help=("Number of iterations to run emcee for, including burn-in and "
              "post-burn iterations."))

    parser.add_argument(
        '--smooth-times',
        '-S',
        dest='smooth_times',
        type=int,
        const=0,
        default=-1,
        nargs='?',
        action='store',
        help=("Add this many more fictitious observations between the first "
              "and last observed times. Setting this value to `0` will "
              "guarantee that all observed bands/instrument/system "
              "combinations have a point at all observed epochs."))

    parser.add_argument(
        '--extrapolate-time',
        '-E',
        dest='extrapolate_time',
        type=float,
        default=0.0,
        nargs='*',
        help=(
            "Extend model light curves this many days before/after "
            "first/last observation. Can be a list of two elements, in which "
            "case the first element is the amount of time before the first "
            "observation to extrapolate, and the second element is the amount "
            "of time before the last observation to extrapolate. Value is set "
            "to `0.0` days if option not set, `100.0` days "
            "by default if no arguments are given."))

    parser.add_argument(
        '--limit-fitting-mjds',
        '-L',
        dest='limit_fitting_mjds',
        type=float,
        default=False,
        nargs=2,
        help=(
            "Only include observations with MJDs within the specified range, "
            "e.g. `-L 54123 54234` will exclude observations outside this "
            "range. If specified without an argument, any upper limit "
            "observations before the last upper limit before the first "
            "detection in a given band will not be included in the fitting."))

    parser.add_argument(
        '--suffix',
        '-s',
        dest='suffix',
        default='',
        help=("Append custom string to output file name to prevent overwrite"))

    parser.add_argument(
        '--num-walkers',
        '-N',
        dest='num_walkers',
        type=int,
        default=50,
        help=("Number of walkers to use in emcee, must be at least twice the "
              "total number of free parameters within the model."))

    parser.add_argument(
        '--num-temps',
        '-T',
        dest='num_temps',
        type=int,
        default=1,
        help=("Number of temperatures to use in the parallel-tempered emcee "
              "sampler. `-T 1` is equivalent to the standard "
              "EnsembleSampler."))

    parser.add_argument(
        '--no-fracking',
        dest='fracking',
        default=True,
        action='store_false',
        help=("Setting this flag will skip the `fracking` step of the "
              "optimization process."))

    parser.add_argument(
        '--quiet',
        dest='quiet',
        default=False,
        action='store_true',
        help=("Print minimal output upon execution. Don't display our "
              "amazing logo :-("))

    parser.add_argument(
        '--no-copy-at-launch',
        dest='copy',
        default=True,
        action='store_false',
        help=("Setting this flag will prevent MOSFiT from copying the user "
              "file hierarchy (models/modules/jupyter) to the current working "
              "directory before fitting."))

    parser.add_argument(
        '--force-copy-at-launch',
        dest='force_copy',
        default=False,
        action='store_true',
        help=("Setting this flag will force MOSFiT to overwrite the user "
              "file hierarchy (models/modules/jupyter) to the current working "
              "directory. User will be prompted before being allowed to run "
              "with this flag."))

    parser.add_argument(
        '--offline',
        dest='offline',
        default=False,
        action='store_true',
        help=("MOSFiT will only use cached data and will not attempt to use "
              "any online resources."))

    parser.add_argument(
        '--frack-step',
        '-f',
        dest='frack_step',
        type=int,
        default=50,
        help=("Perform `fracking` every this number of steps while in the "
              "burn-in phase of the fitting process."))

    parser.add_argument(
        '--post-burn',
        '-p',
        dest='post_burn',
        type=int,
        default=500,
        help=("Run emcee this many more iterations after the burn-in phase. "
              "The burn-in phase will thus be run for (i - p) iterations, "
              "where i is the total number of iterations set with `-i` and "
              "p is the value of this parameter."))

    parser.add_argument(
        '--upload',
        '-u',
        dest='upload',
        default=False,
        action='store_true',
        help=("Upload results of MOSFiT to appropriate Open Catalog. If "
              "MOSFiT is only supplied with `-u` and no other arguments, it "
              "will upload the results of the latest run."))

    parser.add_argument(
        '--run-until-converged',
        '-R',
        dest='run_until_converged',
        type=float,
        default=False,
        const=10.0,
        nargs='?',
        help=("Run each model until the autocorrelation time is measured "
              "accurately and chain has burned in for the specified number "
              "of autocorrelation times [Default: 10.0]. This will run "
              "beyond the specified number of iterations, and is recommended "
              "when the `--upload/-u` flag is set."))

    parser.add_argument(
        '--draw-above-likelihood',
        '-d',
        dest='draw_above_likelihood',
        type=float,
        default=False,
        const=0.0,
        nargs='?',
        help=("When randomly drawing walkers initially, do not accept a draw "
              "unless a likelihood value is greater than this value. By "
              "default, any score greater than the likelihood floor will be "
              "retained."))

    parser.add_argument(
        '--set-upload-token',
        dest='set_upload_token',
        const=True,
        default=False,
        nargs='?',
        help=("Set the upload token. If given an argument, expects a 64-"
              "character token. If given no argument, MOSFiT will prompt "
              "the user to provide a token."))

    parser.add_argument(
        '--ignore-upload-quality',
        dest='check_upload_quality',
        default=True,
        action='store_false',
        help=("Ignore all quality checks when uploading fits."))

    parser.add_argument(
        '--travis',
        dest='travis',
        default=False,
        action='store_true',
        help=("Alters the printing of output messages such that a new line is "
              "generated with each message. Users are unlikely to need this "
              "parameter; it is included as Travis requires new lines to be "
              "produed to detected program output."))

    parser.add_argument(
        '--variance-for-each',
        dest='variance_for_each',
        default=[],
        nargs='+',
        help=("Create a separate `Variance` for each type of observation "
              "specified. Currently `band` is the only valid option."))

    return parser


def main():
    """Main function for MOSFiT."""
    dir_path = os.path.dirname(os.path.realpath(__file__))

    parser = get_parser()

    args = parser.parse_args()

    prt = Printer(wrap_length=100, quiet=args.quiet)
    args.printer = prt

    args.write = True

    if (isinstance(args.extrapolate_time, list) and
            len(args.extrapolate_time) == 0):
        args.extrapolate_time = 100.0

    if len(args.band_list) and args.smooth_times == -1:
        prt.wrapped('Enabling -S as extra bands were defined.')
        args.smooth_times = 0

    changed_iterations = False
    if args.iterations == -1:
        if len(args.events) == 1 and args.events[0] == '':
            changed_iterations = True
            args.iterations = 0
        else:
            args.iterations = 1000

    if is_master():
        # Get hash of ourselves
        mosfit_hash = get_mosfit_hash()

        # Print our amazing ASCII logo.
        if not args.quiet:
            with open(os.path.join(dir_path, 'logo.txt'), 'r') as f:
                logo = f.read()
                firstline = logo.split('\n')[0]
                if isinstance(firstline, bytes):
                    firstline = firstline.decode('utf-8')
                width = len(normalize('NFC', firstline))
                print(logo)
            print('### MOSFiT -- Version {} ({}) ###'
                  .format(__version__, mosfit_hash).center(width))
            print('Authored by James Guillochon & Matt Nicholl'.center(width))
            print('Released under the MIT license'.center(width))
            print('https://github.com/guillochon/MOSFiT\n'.center(width))

        # Get/set upload token
        upload_token = ''
        get_token_from_user = False
        if args.set_upload_token:
            if args.set_upload_token is not True:
                upload_token = args.set_upload_token
            get_token_from_user = True

        upload_token_path = os.path.join(dir_path, 'cache', 'dropbox.token')

        # Perform a few checks on upload before running (to keep size
        # manageable)
        if args.upload and args.smooth_times > 100:
            response = prt.prompt(
                'You have set the `--smooth-times` flag to a value '
                'greater than 100, which will disable uploading. Continue '
                'with uploading disabled?')
            if response:
                args.upload = False
            else:
                sys.exit()

        if args.upload and args.num_walkers * args.num_temps > 200:
            response = prt.prompt(
                'The product of `--num-walkers` and `--num-temps` exceeds '
                '200, which will disable uploading. Continue '
                'with uploading disabled?')
            if response:
                args.upload = False
            else:
                sys.exit()

        if args.upload:
            if not os.path.isfile(upload_token_path):
                get_token_from_user = True
            else:
                with open(upload_token_path, 'r') as f:
                    upload_token = f.read().splitlines()
                    if len(upload_token) != 1:
                        get_token_from_user = True
                    elif len(upload_token[0]) != 64:
                        get_token_from_user = True
                    else:
                        upload_token = upload_token[0]

        if get_token_from_user:
            if args.travis:
                upload_token = ('1234567890abcdefghijklmnopqrstuvwxyz'
                                '1234567890abcdefghijklmnopqr')
            while len(upload_token) != 64:
                prt.wrapped(
                    "No upload token found! Please visit "
                    "https://sne.space/mosfit/ to obtain an upload "
                    "token for MOSFiT.")
                upload_token = prt.prompt(
                    "Please paste your Dropbox token, then hit enter:",
                    kind='string')
                if len(upload_token) != 64:
                    prt.wrapped(
                        'Error: Token must be exactly 64 characters in '
                        'length.')
                    continue
                break
            with open(upload_token_path, 'w') as f:
                f.write(upload_token)

        if args.upload:
            prt.wrapped(
                "Upload flag set, will upload results after completion.")
            prt.wrapped("Dropbox token: " + upload_token)

        args.upload_token = upload_token

        if changed_iterations:
            prt.wrapped("No events specified, setting iterations to 0.")

        # Create the user directory structure, if it doesn't already exist.
        if args.copy:
            prt.wrapped(
                'Copying MOSFiT folder hierarchy to current working directory '
                '(disable with --no-copy-at-launch).')
            fc = False
            if args.force_copy:
                fc = prt.prompt(
                    "The flag `--force-copy-at-launch` has been set. Do you "
                    "really wish to overwrite your local model/module/jupyter "
                    "file hierarchy? This action cannot be reversed.", width)
            if not os.path.exists('jupyter'):
                os.mkdir(os.path.join('jupyter'))
            if not os.path.isfile(os.path.join('jupyter',
                                               'mosfit.ipynb')) or fc:
                shutil.copy(
                    os.path.join(dir_path, 'jupyter', 'mosfit.ipynb'),
                    os.path.join(os.getcwd(), 'jupyter', 'mosfit.ipynb'))

            # Disabled for now as external modules don't work with MPI.
            # if not os.path.exists('modules'):
            #     os.mkdir(os.path.join('modules'))
            # module_dirs = next(os.walk(os.path.join(dir_path, 'modules')))[1]
            # for mdir in module_dirs:
            #     if mdir.startswith('__'):
            #         continue
            #     mdir_path = os.path.join('modules', mdir)
            #     if not os.path.exists(mdir_path):
            #         os.mkdir(mdir_path)

            if not os.path.exists('models'):
                os.mkdir(os.path.join('models'))
            model_dirs = next(os.walk(os.path.join(dir_path, 'models')))[1]
            for mdir in model_dirs:
                if mdir.startswith('__'):
                    continue
                mdir_path = os.path.join('models', mdir)
                if not os.path.exists(mdir_path):
                    os.mkdir(mdir_path)
                model_files = next(
                    os.walk(os.path.join(dir_path, 'models', mdir)))[2]
                for mfil in model_files:
                    fil_path = os.path.join(os.getcwd(), 'models', mdir, mfil)
                    if os.path.isfile(fil_path) and not fc:
                        continue
                    shutil.copy(
                        os.path.join(dir_path, 'models', mdir, mfil),
                        os.path.join(fil_path))

    # Then, fit the listed events with the listed models.
    fitargs = vars(args)
    Fitter().fit_events(**fitargs)


if __name__ == "__main__":
    main()
