library ieee;
use ieee.NUMERIC_STD.all;
use ieee.std_logic_1164.all;
use std.textio.all;

entity cfar_detector_tb is
end cfar_detector_tb;

architecture TB_ARCHITECTURE of cfar_detector_tb is
    component cfar_detector
        port (
            clk            : in  std_logic;
            reset          : in  std_logic;
            s_axis_tvalid  : in  std_logic;
            s_axis_tready  : out std_logic;
            s_axis_tdata_i : in  signed(31 downto 0);
            s_axis_tdata_q : in  signed(31 downto 0);
            s_axis_tlast   : in  std_logic;
            m_axis_tvalid  : out std_logic;
            m_axis_tready  : in  std_logic;
            m_axis_tdata   : out std_logic;
            m_axis_tlast   : out std_logic
        );
    end component;

    -- Signals
    signal clk            : std_logic;
    signal reset          : std_logic;
    signal s_axis_tvalid  : std_logic;
    signal s_axis_tready  : std_logic;
    signal s_axis_tdata_i : signed(31 downto 0);
    signal s_axis_tdata_q : signed(31 downto 0);
    signal s_axis_tlast   : std_logic;
    signal m_axis_tvalid  : std_logic;
    signal m_axis_tready  : std_logic;
    signal m_axis_tdata   : std_logic;
    signal m_axis_tlast   : std_logic;
    signal simulationActive : boolean := true;

begin
    -- UUT instantiation
    UUT : cfar_detector
        port map (
            clk            => clk,
            reset          => reset,
            s_axis_tvalid  => s_axis_tvalid,
            s_axis_tready  => s_axis_tready,
            s_axis_tdata_i => s_axis_tdata_i,
            s_axis_tdata_q => s_axis_tdata_q,
            s_axis_tlast   => s_axis_tlast,
            m_axis_tvalid  => m_axis_tvalid,
            m_axis_tready  => m_axis_tready,
            m_axis_tdata   => m_axis_tdata,
            m_axis_tlast   => m_axis_tlast
        );

    -- Downstream always ready
    m_axis_tready <= '1';

    -- Clock generator (5 MHz — 200 ns period)
    clock_gen : process
    begin
        while simulationActive loop
            clk <= '0'; wait for 100 ns;
            clk <= '1'; wait for 100 ns;
        end loop;
        wait;
    end process;

    -- Stimulus: read cfar_input.csv line-by-line, drive slave AXI-S
    stimulus : process
        file     infile  : text open read_mode is "cfar_input.csv";
        variable inline  : line;
        variable i_val   : integer;
        variable q_val   : integer;
        variable comma   : character;
    begin
        -- Initialize inputs
        s_axis_tvalid <= '0';
        s_axis_tdata_i <= (others => '0');
        s_axis_tdata_q <= (others => '0');
        s_axis_tlast   <= '0';

        -- Reset
        reset <= '1';
        wait for 400 ns;
        reset <= '0';
        wait for 400 ns;

        -- Feed each line of cfar_input.csv into the CFAR
        while not endfile(infile) loop
            readline(infile, inline);
            read(inline, i_val);
            read(inline, comma);
            read(inline, q_val);

            s_axis_tdata_i <= to_signed(i_val, 32);
            s_axis_tdata_q <= to_signed(q_val, 32);
            s_axis_tvalid <= '1';

            -- One clock per sample (CFAR is always ready)
            wait until rising_edge(clk);
        end loop;

        -- Deassert after last sample and drain
        s_axis_tvalid <= '0';
        wait for 1 us;
        simulationActive <= false;
        wait;
    end process;

    -- File output: write m_axis_tdata to cfar_output.csv when tvalid high.
    -- One line per valid output, value is '0' or '1'.
    file_output : process
        file     outfile : text open write_mode is "cfar_output.csv";
        variable outline : line;
    begin
        wait until rising_edge(clk);
        if m_axis_tvalid = '1' then
            if m_axis_tdata = '1' then
                write(outline, string'("1"));
            else
                write(outline, string'("0"));
            end if;
            writeline(outfile, outline);
        end if;
    end process;

end TB_ARCHITECTURE;

configuration TESTBENCH_FOR_cfar_detector of cfar_detector_tb is
    for TB_ARCHITECTURE
        for UUT : cfar_detector
            use entity work.cfar_detector(arch);
        end for;
    end for;
end TESTBENCH_FOR_cfar_detector;
