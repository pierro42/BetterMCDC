# -*- coding: utf-8 -*-
"""
MC/DC (Modified Condition / Decision Coverage) test-set generator for a
Boolean expression.

Modules:
  decision     input language -> Decision
  tree         expression tree, evaluation, independence-pair definitions
               ([S2] 3.1.1 unique-cause, 3.1.2 masking by graph coloring,
               3.2.2 unique-cause + masking)
  exact        whole-truth-table engine and minimal set ([S2] 5.1 bounds)
  pair_search  engine for large expressions (no truth table)
  analysis     chooses the engine
  report       text / CSV output
  scenario     test scenario file from a TOML template

[S2] DOT/FAA/AR-01/18, Chilenski, April 2001.
"""

from .analysis import DEFAULT_MAX_EXACT, Analysis, analyse_mcdc
from .decision import Decision, parse_decision
from .exact import independence_pairs, lower_bound, minimal_mcdc_set
from .report import print_mcdc_summary, print_table
from .scenario import load_template, output_filename, render_scenario
from .exact import test_rows
from .tree import (MODES, PAIR_CHECK, canonical, executed_inputs, is_masking_pair,
                   is_unique_cause_masking_pair, is_unique_cause_pair, node_masks,
                   row_number, tree_xor, truth_table)

__all__ = ["DEFAULT_MAX_EXACT", "Analysis", "analyse_mcdc", "Decision", "parse_decision",
           "independence_pairs", "lower_bound", "minimal_mcdc_set", "print_mcdc_summary",
           "print_table", "MODES", "PAIR_CHECK", "is_masking_pair",
           "is_unique_cause_masking_pair", "is_unique_cause_pair", "node_masks", "tree_xor",
           "canonical", "executed_inputs", "test_rows",
           "row_number", "truth_table", "load_template", "output_filename",
           "render_scenario"]
