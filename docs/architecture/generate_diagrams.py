"""
Generate architecture diagrams for the radar-dsp project using matplotlib.

Produces three images in docs/architecture/:
  - top_level.png               — full signal chain block diagram
  - dds_chirp_internal.png      — DDS chirp generator internal blocks
  - dds_chirp_state_machine.png — Control FSM for the DDS

Run: python generate_diagrams.py
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle


OUT_DIR = os.path.dirname(__file__)

# Color palette — dark-background friendly
BLOCK_FILL  = '#2d3748'
BLOCK_EDGE  = '#81a1c1'
TEXT_COLOR  = '#eceff4'
ARROW_COLOR = '#88c0d0'
BG_COLOR    = '#1e222a'
ACCENT      = '#ebcb8b'


def make_block(ax, x, y, w, h, text, fontsize=11, fill=BLOCK_FILL):
    """Draw a rounded rectangle with centered text."""
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.1",
        linewidth=1.5, facecolor=fill, edgecolor=BLOCK_EDGE)
    ax.add_patch(box)
    ax.text(x, y, text, ha='center', va='center',
            color=TEXT_COLOR, fontsize=fontsize, weight='bold')


def make_arrow(ax, x1, y1, x2, y2, label=None, label_offset=(0.0, 0.15),
               style='->', linewidth=1.8):
    """Draw an arrow from (x1, y1) to (x2, y2) with optional label."""
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
# 1. Top-level signal chain block diagram
# =============================================================================
def draw_top_level():
    fig, ax = setup_axes((12, 4), (0, 14), (0, 5),
                         'radar-dsp Top-Level Signal Chain')

    # Blocks
    make_block(ax, 2.5, 3, 2.5, 1.2, 'DDS Chirp\nGenerator')
    make_block(ax, 6.5, 3, 2.5, 1.2, 'Matched\nFilter\n(Complex FIR)')
    make_block(ax, 10.5, 3, 2.5, 1.2, 'CFAR\nDetector\n(CA-CFAR)')

    # Trigger input
    make_arrow(ax, 0.3, 3, 1.25, 3, label='trigger', label_offset=(0, 0.3))

    # Between-block arrows
    make_arrow(ax, 3.75, 3, 5.25, 3, label='I/Q (AXI-S)')
    make_arrow(ax, 7.75, 3, 9.25, 3, label='|MF|² (AXI-S)')

    # Output
    make_arrow(ax, 11.75, 3, 13.7, 3, label='detections',
               label_offset=(0, 0.3))

    # Coefficient ROM feeding matched filter
    make_block(ax, 6.5, 0.8, 2.2, 0.7,
               'Reference Chirp Coef ROM', fontsize=9,
               fill='#3b4252')
    make_arrow(ax, 6.5, 1.15, 6.5, 2.4,
               label='coefs', label_offset=(0.45, 0))

    # Caption
    ax.text(7, 4.5,
            'All blocks stream Q1.15 complex samples over AXI-Stream.',
            ha='center', va='center',
            color=TEXT_COLOR, fontsize=10, style='italic')

    fig.savefig(os.path.join(OUT_DIR, 'top_level.png'),
                dpi=160, bbox_inches='tight',
                facecolor=BG_COLOR)
    plt.close(fig)
    print('Saved top_level.png')


# =============================================================================
# 2. DDS Chirp Generator internal block diagram
# =============================================================================
def draw_dds_internal():
    fig, ax = setup_axes((13, 7), (0, 14), (0, 9),
                         'DDS Chirp Generator — Internal Architecture')

    # Control FSM (top)
    make_block(ax, 2.2, 7.5, 2.4, 1.0, 'Control FSM\n(IDLE / GEN)')

    # Sample counter
    make_block(ax, 2.2, 5.5, 2.4, 1.0, 'Sample Counter\n0 .. N-1')

    # FCW ramp
    make_block(ax, 6.5, 5.5, 2.6, 1.0, 'FCW Ramp\nlinear sweep\nfcw_start → fcw_end')

    # Phase accumulator
    make_block(ax, 10.7, 5.5, 2.4, 1.0, 'Phase\nAccumulator\n(32-bit)')

    # CORDIC
    make_block(ax, 10.7, 2.8, 2.8, 1.4,
               'CORDIC\nphase → (sin, cos)\n16-stage pipeline')

    # AXI-S wrapper
    make_block(ax, 10.7, 0.8, 2.8, 0.8, 'AXI-Stream Out (I, Q)',
               fontsize=9, fill='#3b4252')

    # Trigger in
    make_arrow(ax, 0.3, 7.5, 1.0, 7.5, label='start',
               label_offset=(0, 0.25))

    # FSM → sample counter (enable)
    make_arrow(ax, 2.2, 7.0, 2.2, 6.0, label='enable',
               label_offset=(0.4, 0))

    # FSM → busy / done outputs
    make_arrow(ax, 3.4, 7.8, 13.7, 7.8, label='busy',
               label_offset=(0, 0.25))
    make_arrow(ax, 3.4, 7.2, 13.7, 7.2, label='done',
               label_offset=(0, -0.25))

    # Sample counter → FCW ramp
    make_arrow(ax, 3.4, 5.5, 5.2, 5.5, label='sample_idx')

    # FCW ramp → Phase accumulator
    make_arrow(ax, 7.8, 5.5, 9.5, 5.5, label='fcw[n]')

    # Phase accumulator → CORDIC
    make_arrow(ax, 10.7, 5.0, 10.7, 3.5, label='phase',
               label_offset=(0.5, 0))

    # CORDIC → AXI-S out
    make_arrow(ax, 10.7, 2.1, 10.7, 1.2, label='I, Q',
               label_offset=(0.4, 0))

    # AXI-S output arrow
    make_arrow(ax, 12.1, 0.8, 13.7, 0.8, label='tdata')

    # Feedback loop on phase accumulator
    make_arrow(ax, 11.9, 5.5, 12.4, 5.5, style='->',
               linewidth=1.2)
    ax.annotate('', xy=(11.9, 5.9), xytext=(12.4, 5.9),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=1.2))
    ax.plot([12.4, 12.4], [5.5, 5.9], color=ARROW_COLOR, linewidth=1.2)
    ax.text(12.55, 5.7, 'accum\nfeedback', color=ACCENT,
            fontsize=8, style='italic', va='center')

    # Legend / caption
    ax.text(7, 8.5,
            'Phase accumulator advances by FCW each clock.\n'
            'Ramping FCW over time produces a linearly-swept frequency (the chirp).',
            ha='center', va='center',
            color=TEXT_COLOR, fontsize=10, style='italic')

    fig.savefig(os.path.join(OUT_DIR, 'dds_chirp_internal.png'),
                dpi=160, bbox_inches='tight',
                facecolor=BG_COLOR)
    plt.close(fig)
    print('Saved dds_chirp_internal.png')


# =============================================================================
# 3. DDS Chirp Generator state machine
# =============================================================================
def draw_dds_state_machine():
    fig, ax = setup_axes((10, 6), (0, 10), (0, 6),
                         'DDS Chirp Generator — Control FSM')

    # States as circles
    def draw_state(x, y, label, r=0.8):
        c = Circle((x, y), r, facecolor=BLOCK_FILL,
                   edgecolor=BLOCK_EDGE, linewidth=2.0)
        ax.add_patch(c)
        ax.text(x, y, label, ha='center', va='center',
                color=TEXT_COLOR, fontsize=13, weight='bold')
        return (x, y, r)

    idle = draw_state(2.5, 3, 'IDLE')
    gen  = draw_state(7.5, 3, 'GEN')

    # Reset arrow (entering IDLE from nothing)
    make_arrow(ax, 0.6, 3, 1.7, 3, label='reset',
               label_offset=(0, 0.3))

    # IDLE → GEN (start)
    ax.annotate('', xy=(6.75, 3.4), xytext=(3.25, 3.4),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=2.0, mutation_scale=18,
                                connectionstyle='arc3,rad=-0.25'))
    ax.text(5, 4.5, 'start = 1', color=ACCENT, fontsize=11,
            ha='center', style='italic')

    # GEN → IDLE (samples_done)
    ax.annotate('', xy=(3.25, 2.6), xytext=(6.75, 2.6),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=2.0, mutation_scale=18,
                                connectionstyle='arc3,rad=-0.25'))
    ax.text(5, 1.5, 'sample_idx == N-1', color=ACCENT, fontsize=11,
            ha='center', style='italic')

    # Self-loop on GEN
    ax.annotate('', xy=(8.25, 3.55), xytext=(8.55, 3.75),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=1.8, mutation_scale=16,
                                connectionstyle='arc3,rad=1.3'))
    ax.text(9.0, 3.9, 'else', color=ACCENT, fontsize=10,
            style='italic', va='center')

    # Self-loop on IDLE
    ax.annotate('', xy=(1.75, 3.55), xytext=(1.45, 3.75),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                linewidth=1.8, mutation_scale=16,
                                connectionstyle='arc3,rad=-1.3'))
    ax.text(0.95, 3.9, 'start = 0', color=ACCENT, fontsize=10,
            style='italic', va='center', ha='right')

    # Caption
    ax.text(5, 0.5,
            'IDLE: wait for start. Phase accumulator held at 0, sample counter = 0, busy = 0.\n'
            'GEN:  advance phase by fcw each clock, increment sample counter, busy = 1.',
            ha='center', va='center',
            color=TEXT_COLOR, fontsize=9, style='italic')

    fig.savefig(os.path.join(OUT_DIR, 'dds_chirp_state_machine.png'),
                dpi=160, bbox_inches='tight',
                facecolor=BG_COLOR)
    plt.close(fig)
    print('Saved dds_chirp_state_machine.png')


if __name__ == '__main__':
    draw_top_level()
    draw_dds_internal()
    draw_dds_state_machine()
    print('All diagrams saved to', os.path.abspath(OUT_DIR))
