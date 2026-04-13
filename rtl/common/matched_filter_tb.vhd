library ieee;
use ieee.NUMERIC_STD.all;
use ieee.std_logic_1164.all;
use std.textio.all;

entity matched_filter_tb is
end matched_filter_tb;

architecture TB_ARCHITECTURE of matched_filter_tb is
	-- Component declaration of the tested unit
	component matched_filter
	port(
		clk    : in std_logic; -- Clock signal
    reset  : in std_logic; -- Reset signal (active high)
    s_axis_tvalid : in std_logic; -- Valid signal indicating input data is valid
    s_axis_tready : out std_logic; -- Ready signal indicating the matched filter is ready to receive data
    s_axis_tdata_i : in signed(15 downto 0); -- I component input (16-bit signed)
    s_axis_tdata_q : in signed(15 downto 0); -- Q component input (16-bit signed)
    s_axis_tlast : in std_logic; -- Last signal indicating the last sample of the input burst
    m_axis_tvalid : out std_logic; -- Valid signal indicating output data is valid
    m_axis_tready : in std_logic; -- Ready signal indicating downstream is ready to receive
    m_axis_tdata_i : out signed(31 downto 0); -- I component output (32-bit signed)
    m_axis_tdata_q : out signed(31 downto 0); -- Q component output (32-bit signed)
    m_axis_tlast : out std_logic -- Last signal indicating the last sample of the output burst
    	);
    end component;

	-- Stimulus signals - signals mapped to the input and inout ports of tested entity
	signal clk : STD_LOGIC;
	signal    reset  :  std_logic; -- Reset signal (active high)
    signal s_axis_tvalid :  std_logic; -- Valid signal indicating input data is valid
    signal s_axis_tready :  std_logic; -- Ready signal indicating the matched filter is ready to receive data
    signal s_axis_tdata_i :  signed(15 downto 0); -- I component input (16-bit signed)
    signal s_axis_tdata_q :  signed(15 downto 0); -- Q component input (16-bit signed)
    signal s_axis_tlast :  std_logic; -- Last signal indicating the last sample of the input burst
    signal m_axis_tvalid :  std_logic; -- Valid signal indicating output data is valid
    signal m_axis_tready :  std_logic; -- Ready signal indicating downstream is ready to receive
    signal m_axis_tdata_i :  signed(31 downto 0); -- I component output (32-bit signed)
    signal m_axis_tdata_q :  signed(31 downto 0); -- Q component output (32-bit signed)
    signal m_axis_tlast :  std_logic; -- Last signal indicating the last sample of the output burst
    signal simulationActive : boolean := true;

    
begin

	-- Unit Under Test port map
	UUT : matched_filter
		port map (
    clk    => clk, -- Clock signal
    reset  => reset, -- Reset signal (active high) 
    s_axis_tvalid => s_axis_tvalid, -- Valid signal indicating input data is valid
    s_axis_tready => s_axis_tready, -- Ready signal indicating the matched filter is ready to receive data
    s_axis_tdata_i => s_axis_tdata_i, -- I component input (16-bit signed)
    s_axis_tdata_q => s_axis_tdata_q, -- Q component input (16-bit signed)
    s_axis_tlast => s_axis_tlast, -- Last signal indicating the last sample of the input burst
    m_axis_tvalid => m_axis_tvalid, -- Valid signal indicating output data is valid
    m_axis_tready => m_axis_tready, -- Ready signal indicating downstream is ready to receive
    m_axis_tdata_i => m_axis_tdata_i, -- I component output (32-bit signed)
    m_axis_tdata_q => m_axis_tdata_q, -- Q component output (32-bit signed)
    m_axis_tlast => m_axis_tlast -- Last signal indicating the last sample of the output burst
		);
	-- Add your stimulus here ...
	    m_axis_tready <= '1'; -- Always ready to receive data
	process	 

	begin	 
	while simulationActive loop	   
		
			clk <='0'; wait for 100 ns;
			clk <='1'; wait for 100 ns;
		end loop;
		wait;  
	end process;	
	
	stimulus : process
	    file     infile  : text open read_mode is "mf_input.csv";
	    variable inline  : line;
	    variable i_val   : integer;
	    variable q_val   : integer;
	    variable comma   : character;
	begin
	    -- Initialize inputs
	    s_axis_tvalid <= '0';
	    s_axis_tdata_i <= (others => '0');
	    s_axis_tdata_q <= (others => '0');
	    s_axis_tlast <= '0';

	    -- Reset
	    reset <= '1';
	    wait for 400 ns;
	    reset <= '0';
	    wait for 400 ns;

	    -- Feed each line of mf_input.csv into the matched filter
	    while not endfile(infile) loop
	        -- Read one line: "i_value,q_value"
	        readline(infile, inline);
	        read(inline, i_val);
	        read(inline, comma);  -- consume the comma
	        read(inline, q_val);

	        -- Put sample on the bus
	        s_axis_tdata_i <= to_signed(i_val, 16);
	        s_axis_tdata_q <= to_signed(q_val, 16);
	        s_axis_tvalid <= '1';

	        -- Wait for the filter to accept (tready high in IDLE)
	        wait until rising_edge(clk) and s_axis_tready = '1';

	        -- Deassert tvalid and wait for MAC + OUTPUT to complete
	        s_axis_tvalid <= '0';
	        wait until rising_edge(clk) and m_axis_tvalid = '1';

	        -- One extra clock to let the output settle
	        wait until rising_edge(clk);
	    end loop;

	    -- Wait a bit then end
	    wait for 1 us;
	    simulationActive <= false;
	    wait;
	end process;

-- File output: write each output I/Q to CSV when m_axis_tvalid is high.
file_output : process
    file     outfile : text open write_mode is "mf_output.csv";
    variable outline : line;
begin
    wait until rising_edge(clk);
    if m_axis_tvalid = '1' then
        write(outline, integer'image(to_integer(m_axis_tdata_i)));
        write(outline, string'(","));
        write(outline, integer'image(to_integer(m_axis_tdata_q)));
        writeline(outfile, outline);
    end if;
end process;

end TB_ARCHITECTURE;

configuration TESTBENCH_FOR_matched_filter of matched_filter_tb is
	for TB_ARCHITECTURE
		for UUT : matched_filter
			use entity work.matched_filter(arch);
		end for;
	end for;
end TESTBENCH_FOR_matched_filter;

