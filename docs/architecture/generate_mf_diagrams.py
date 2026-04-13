"""
Generate matched filter architecture diagrams.

Produces:
  - matched_filter_internal.png    — time-multiplexed FIR block diagram
  - matched_filter_state_machine.png — control FSM

Run: python generate_mf_diagrams.py
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

OUT_DIR = os.path.dirname(__file__)

BLOCK_FILL  = '#2d3748'
BLOCK_EDGE  = '#81a1c1'
TEXT_COLOR   = '#eceff4'
ARROW_COLOR = '#88c0d0'
BG_COLOR    = '#1e222a'
ACCENT      = '#ebcb8b'
ACCENT2     = '#a3be8c'


def make_block(ax, x, y, w, h, text, fontsize=10, fill=BLOCK_FILL):
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.1",
        linewidth=1.5, facecolor=fill, edgecolor=BLOCK_EDGE)
    ax.add_patch(box)
    ax.text(x, y, text, ha='center', va='center',
            color=TEXT_COLOR, fontsize=fontsize, weight='bold')


def make_arrow(ax, x1, y1, x2, y2, label=None, label_offset=(0.0, 0.15),
               style='->', linewidth=1.8):
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                             arrowstyle=style,
                             color=ARROW_COLOR,
                             linewidth=linewidth,
                             mutation_scale=18)
    ax.add_patch(arrow)
    if label:
        mx = (x1 + x2) / 2 + label_offset[0]
        my = (y1 + y2) / 2 + label_offset[1]
        ax.text(mx, my, label, ha='center', va='center',
                color=ACCENT, fontsize=9, style='italic')


def setup_axes(figsize, xlim, ylim, title):
    fig, ax = plt.subplots(figsize=figsize, facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, color=TEXT_COLOR, fontsize=14, weight='bold', pad=15)
    return fig, ax


# =============================================================================
# 1. Matched Filter internal block diagram (time-multiplexed)
# =============================================================================
def draw_mf_internal():
    fig, ax = setup_axes((14, 10), (0, 14), (0, 12),
                         'Matched Filter — Time-Multiplexed Architecture')

    # AXI-S input
    ax.text(0.5, 10.5, 'AXI-S in\n(from DDS)',
            ha='center', va='center', color=ACCENT2, fontsize=10, style='italic')
    make_arrow(ax, 1.3, 10.5, 2.5, 10.5)

    # Input sample buffer
    make_block(ax, 4.5, 10.5, 3.5, 1.2,
               'Input Sample Buffer\n(64-deep shift register)\nstores recent I/Q samples')

    # Load arrow
    make_arrow(ax, 4.5, 9.9, 4.5, 8.8, label='sample[k]',
               label_offset=(0.7, 0))

    # MUX
    make_block(ax, 4.5, 8.0, 2.5, 1.0, 'MUX\nselects sample[k]', fontsize=9)

    # Tap counter driving MUX
    make_block(ax, 1.5, 8.0, 2.0, 0.8, 'Tap Counter\nk: 0..63', fontsize=9,
               fill='#3b4252')
    make_arrow(ax, 2.5, 8.0, 3.25, 8.0, label='k', label_offset=(0, 0.25))

    # MUX to MAC
    make_arrow(ax, 4.5, 7.5, 4.5, 6.3, label='sample[k]',
               label_offset=(0.7, 0))

    # Complex MAC
    make_block(ax, 4.5, 5.3, 3.5, 1.4,
               'Complex MAC\n4 real multiplies + 2 adds\n(4 DSP48E2 slices)')

    # Coefficient ROM
    make_block(ax, 9.5, 5.3, 3.0, 1.2,
               'Coefficient ROM\n64 entries\ncoef[k] = conj(chirp[63-k])',
               fontsize=9, fill='#3b4252')
    make_arrow(ax, 8.0, 5.3, 5.75, 5.3, label='coef[k]',
               label_offset=(0, 0.3), style='<-')

    # Tap counter to coef ROM
    make_arrow(ax, 1.5, 7.6, 1.5, 5.3, style='->', linewidth=1.2)
    make_arrow(ax, 1.5, 5.3, 8.0, 5.3, label='k',
               label_offset=(0, -0.3), linewidth=1.2)

    # MAC to accumulator
    make_arrow(ax, 4.5, 4.6, 4.5, 3.5, label='product',
               label_offset=(0.6, 0))

    # Accumulator
    make_block(ax, 4.5, 2.7, 3.5, 1.0,
               'Accumulator (48-bit)\nreal_acc += (ac - bd)\nimag_acc += (ad + bc)',
               fontsize=9)

    # Feedback loop on accumulator
    ax.annotate('', xy=(6.25, 3.1), xytext=(6.7, 3.1),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=1.2))
    ax.plot([6.7, 6.7, 6.25], [3.1, 2.3, 2.3], color=ARROW_COLOR, linewidth=1.2)
    ax.text(7.0, 2.7, 'accum\nfeedback', color=ACCENT, fontsize=8,
            style='italic', va='center')

    # Accumulator to output register
    make_arrow(ax, 4.5, 2.2, 4.5, 1.2, label='when k = 63',
               label_offset=(0.8, 0))

    # Output register
    make_block(ax, 4.5, 0.5, 3.5, 0.8,
               'Output Register + AXI-S master', fontsize=9, fill='#3b4252')

    # AXI-S output
    make_arrow(ax, 6.25, 0.5, 7.5, 0.5)
    ax.text(8.5, 0.5, 'AXI-S out\n(to CFAR)',
            ha='center', va='center', color=ACCENT2, fontsize=10, style='italic')

    # Bit width annotations on the right side
    annotations = [
        (12.5, 10.5, 'Input: 16-bit signed\n(Q1.15 complex)'),
        (12.5, 5.3,  'Products: 32-bit signed\n(Q2.30)'),
        (12.5, 2.7,  'Accumulator: 48-bit signed\n(sum of 64 products)'),
        (12.5, 0.5,  'Output: 48-bit or\ntruncated to 32-bit'),
    ]
    for x, y, text in annotations:
        ax.text(x, y, text, ha='center', va='center',
                color='#616e88', fontsize=8, style='italic',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#2e3440',
                          edgecolor='#4c566a', linewidth=0.8))

    # Caption
    ax.text(7, 11.5,
            'Time-multiplexed: one complex MAC reused 64 times per output sample.\n'
            'At 200 kHz sample rate / 100 MHz clock = 500 clocks per sample; needs only 64.',
            ha='center', va='center',
            color=TEXT_COLOR, fontsize=10, style='italic')

    fig.savefig(os.path.join(OUT_DIR, 'matched_filter_internal.png'),
                dpi=160, bbox_inches='tight', facecolor=BG_COLOR)
    plt.close(fig)
    print('Saved matched_filter_internal.png')


# =============================================================================
# 2. Matched Filter state machine
# =============================================================================
def draw_mf_state_machine():
    fig, ax = setup_axes((12, 8), (0, 12), (0, 8),
                         'Matched Filter — Control FSM')

    def draw_state(x, y, label, r=0.9):
        c = Circle((x, y), r, facecolor=BLOCK_FILL,
                   edgecolor=BLOCK_EDGE, linewidth=2.0)
        ax.add_patch(c)
        ax.text(x, y, label, ha='center', va='center',
                color=TEXT_COLOR, fontsize=13, weight='bold')

    # States
    draw_state(2, 5, 'IDLE')
    draw_state(6, 7, 'LOAD')
    draw_state(10, 5, 'MAC')
    draw_state(6, 2.5, 'OUTPUT')

    # Reset arrow
    make_arrow(ax, 0.3, 5, 1.1, 5, label='reset', label_offset=(0, 0.3))

    # IDLE → LOAD (input tvalid)
    ax.annotate('', xy=(5.3, 6.6), xytext=(2.7, 5.6),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=2.0, mutation_scale=18))
    ax.text(3.3, 6.6, 'input tvalid = 1\n(new sample arrived)',
            color=ACCENT, fontsize=9, style='italic', ha='center')

    # LOAD → MAC
    ax.annotate('', xy=(9.3, 5.6), xytext=(6.7, 6.6),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=2.0, mutation_scale=18))
    ax.text(8.8, 6.8, 'shift sample into buffer\nclear accumulator\nk <= 0',
            color=ACCENT, fontsize=9, style='italic', ha='center')

    # MAC self-loop
    ax.annotate('', xy=(10.7, 5.7), xytext=(10.9, 5.9),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=1.8, mutation_scale=16,
                                connectionstyle='arc3,rad=1.3'))
    ax.text(11.5, 6.3, 'k < 63\nk <= k + 1',
            color=ACCENT, fontsize=9, style='italic', va='center')

    # MAC → OUTPUT
    ax.annotate('', xy=(6.7, 2.9), xytext=(9.3, 4.6),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=2.0, mutation_scale=18))
    ax.text(9.0, 3.4, 'k = 63\n(MAC complete)',
            color=ACCENT, fontsize=9, style='italic', ha='center')

    # OUTPUT → IDLE
    ax.annotate('', xy=(2.5, 4.3), xytext=(5.3, 2.8),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=2.0, mutation_scale=18))
    ax.text(3.0, 3.0, 'push result\ntvalid <= 1',
            color=ACCENT, fontsize=9, style='italic', ha='center')

    # State descriptions
    descriptions = [
        (2, 1.0, 'IDLE: wait for input.\nAccumulator idle, output invalid.'),
        (6, 0.5, 'LOAD: latch new sample into shift register,\nclear accumulators, reset tap counter.'),
        (10, 1.0, 'MAC: multiply sample[k] × coef[k],\naccumulate, increment k. 64 cycles.'),
        (6, 4.2, ''),
    ]
    for x, y, text in descriptions:
        if text:
            ax.text(x, y, text, ha='center', va='center',
                    color='#616e88', fontsize=8, style='italic')

    fig.savefig(os.path.join(OUT_DIR, 'matched_filter_state_machine.png'),
                dpi=160, bbox_inches='tight', facecolor=BG_COLOR)
    plt.close(fig)
    print('Saved matched_filter_state_machine.png')


if __name__ == '__main__':
    draw_mf_internal()
    draw_mf_state_machine()
    print('All diagrams saved to', os.path.abspath(OUT_DIR))
