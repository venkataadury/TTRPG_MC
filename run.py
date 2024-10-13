from TTRPG_MC import *
from dice import *
import argparse
import time

def main():
    parser = argparse.ArgumentParser(description='TTRPG Monte Carlo')
    parser.add_argument('-n', '--num_trials', type=int, default=2000, help='Number of trials to run (more makes the results more accurate)')
    parser.add_argument('-c', '--charsheet', type=str, help='File containing character sheet')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress output', default=False)
    # Add a no-breakdown option to not give item-wise breakdown
    parser.add_argument('-s', '--short', action='store_true', help='Drop item-wise breakdown', default=False)
    args = parser.parse_args()

    if args.charsheet:
        ch_lv1=CharacterData(args.charsheet,silent=args.quiet)
        if not args.quiet: print("Setup complete")
    else:
        raise ValueError("No character sheet provided")
    
    n_comb=ch_lv1.globals["Combats"]
    n_rounds=ch_lv1.globals["Rounds"]
    short_rests=ch_lv1.globals["ShortRest"].split(",")

    if not args.quiet: print("Starting analysis:")
    if not args.quiet: print("Estimating adventuring day in",args.num_trials,"trials for",n_comb,"combats with short rests before combat IDs",short_rests)
    round_stats=ch_lv1.estimate_adventuring_day(args.num_trials,n_combats=int(n_comb),short_rests=[int(x) for x in short_rests],n_rounds=int(n_rounds))
    if not args.quiet: print("Stats gathered",flush=True)

    summarize_round_statistics(round_stats,breakdown=not args.short)

if __name__ == "__main__":
    start_time = time.time()
    main()
    print("Execution time: %s seconds" % (time.time() - start_time))