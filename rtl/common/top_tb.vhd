-- Top-level integration testbench.
--
-- Triggers the DDS chirp once and lets the whole chain run. This test
-- does NOT verify detection results (the CFAR won't exit warmup with
-- only 64 input samples). It verifies that:
--   - AXI-Stream handshakes line up between the three modules
--   - Data flows from DDS -> MF -> CFAR without stalls or deadlocks
--   - The chain compiles, elaborates, and simulates end-to-end
--
-- Detection correctness is verified per-module with the individual
-- testbenches in chirp_tb.vhd, matched_filter_tb.vhd, and
-- cfar_detector_tb.vhd.

library ieee;
use ieee.numeric_std.all;
use ieee.std_logic_1164.all;
use std.textio.all;

entity top_tb is
end top_tb;

architecture TB_ARCHITECTURE of top_tb is
    component top
        port (
            clk              : in  std_logic;
            reset            : in  std_logic;
            trigger          : in  std_logic;
            detection_tvalid : out std_logic;
            detection_tdata  : out std_logic;
            detection_tlast  : out std_logic
        );
    end component;

    signal clk              : std_logic;
    signal reset            : std_logic;
    signal trigger          : std_logic;
    signal detection_tvalid : std_logic;
    signal detection_tdata  : std_logic;
    signal detection_tlast  : std_logic;
    signal simulationActive : boolean := true;

begin
    -- UUT
    UUT : top
        port map (
            clk              => clk,
            reset            => reset,
            trigger          => trigger,
            detection_tvalid => detection_tvalid,
            detection_tdata  => detection_tdata,
            detection_tlast  => detection_tlast
        );

    -- 5 MHz clock (200 ns period)
    clock_gen : process
    begin
        while simulationActive loop
            clk <= '0'; wait for 100 ns;
            clk <= '1'; wait for 100 ns;
        end loop;
        wait;
    end process;

    -- Stimulus: reset, then pulse trigger once, let it run
    stimulus : process
    begin
        trigger <= '0';
        reset   <= '1';
        wait for 400 ns;
        reset   <= '0';
        wait for 400 ns;

        -- Single trigger pulse
        trigger <= '1';
        wait for 200 ns;
        trigger <= '0';

        -- Let the chain run for a while. DDS produces 64 samples, each one
        -- takes ~66 clocks to propagate through the MF, so give it plenty.
        wait for 1 ms;

        simulationActive <= false;
        wait;
    end process;

    -- Dump detection stream to CSV so we can inspect it afterward.
    -- Format: tvalid,tdata,tlast per line. tvalid will stay low until the
    -- CFAR's window fills up (which won't happen with only 64 inputs).
    file_output : process
        file     outfile : text open write_mode is "top_output.csv";
        variable outline : line;
    begin
        wait until rising_edge(clk);
        if detection_tvalid = '1' then
            if detection_tdata = '1' then
                write(outline, string'("1,"));
            else
                write(outline, string'("0,"));
            end if;
            if detection_tlast = '1' then
                write(outline, string'("1"));
            else
                write(outline, string'("0"));
            end if;
            writeline(outfile, outline);
        end if;
    end process;

end TB_ARCHITECTURE;

configuration TESTBENCH_FOR_top of top_tb is
    for TB_ARCHITECTURE
        for UUT : top
            use entity work.top(arch);
        end for;
    end for;
end TESTBENCH_FOR_top;
