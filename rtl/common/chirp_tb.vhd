library ieee;
use ieee.NUMERIC_STD.all;
use ieee.std_logic_1164.all;
use std.textio.all;

entity chirp_tb is
end chirp_tb;

architecture TB_ARCHITECTURE of chirp_tb is
	-- Component declaration of the tested unit
	component chirp
	port(
		clk    : in std_logic; -- Clock signal
    reset  : in std_logic; -- Reset signal (active high)
    start  : in std_logic; -- Start signal to begin chirp generation
    done   : out std_logic; -- Done signal indicating chirp generation complete
    busy   : out std_logic; -- Busy signal indicating chirp generation in progress
    i_out  : out signed(15 downto 0); -- I component output (16-bit signed)
    q_out  : out signed(15 downto 0); -- Q component output (16-bit signed)
    tvalid : out std_logic; -- Valid signal indicating output data is valid
    tlast  : out std_logic; -- Last signal indicating the last sample of the chirp
    tready : in std_logic -- Ready signal indicating downstream is ready to receive data
    	);
    end component;

	-- Stimulus signals - signals mapped to the input and inout ports of tested entity
	signal clk : STD_LOGIC;
	signal    reset  :  std_logic; -- Reset signal (active high)
    signal start  :  std_logic; -- Start signal to begin chirp generation
    signal done   :  std_logic; -- Done signal indicating chirp generation complete
    signal busy   :  std_logic; -- Busy signal indicating chirp generation in progress
    signal i_out  :  signed(15 downto 0); -- I component output (16-bit signed)
    signal q_out  :  signed(15 downto 0); -- Q component output (16-bit signed)
    signal tvalid :  std_logic; -- Valid signal indicating output data is valid
    signal tlast  :  std_logic; -- Last signal indicating the last sample of the chirp
    signal tready :  std_logic; -- Ready signal indicating downstream is ready to receive data
	signal simulationActive : boolean := true; -- Control signal to end the simulation
begin

	-- Unit Under Test port map
	UUT : chirp
		port map (
    clk    => clk, -- Clock signal
    reset  => reset, -- Reset signal (active high) 
    start  => start, -- Start signal to begin chirp generation
    done   => done, -- Done signal indicating chirp generation complete
    busy   => busy, -- Busy signal indicating chirp generation in progress
    i_out  => i_out, -- I component output (16-bit signed)
    q_out  => q_out, -- Q component output (16-bit signed)
    tvalid => tvalid, -- Valid signal indicating output data is valid
    tlast  => tlast, -- Last signal indicating the last sample of the chirp
    tready => tready -- Ready signal indicating downstream is ready to receive data
		);
	-- Add your stimulus here ...
	    tready <= '1'; -- Always ready to receive data
	process	 

	begin	 
	while simulationActive loop	   
		
			clk <='0'; wait for 100 ns;
			clk <='1'; wait for 100 ns;
		end loop;
		wait;  
	end process;	
	
	process 
	begin	 		  

    reset <= '1'; wait for 400 ns;
    reset <= '0'; wait for 400 ns;
    
    start <= '1'; wait for 400 ns;
    start <= '0'; wait for 400 ns;
	wait for 20 us;


    simulationActive <= false; -- End the simulation after the test sequence
	wait;
end process;

-- File output: write each I/Q sample to a CSV when tvalid is high.
-- The file is created in whatever directory you run GHDL from.
-- Each line is: i_value,q_value (signed decimal integers).
file_output : process
    file     outfile : text open write_mode is "chirp_output.csv";
    variable outline : line;
begin
    wait until rising_edge(clk);
    if tvalid = '1' then
        write(outline, integer'image(to_integer(i_out)));
        write(outline, string'(","));
        write(outline, integer'image(to_integer(q_out)));
        writeline(outfile, outline);
    end if;
end process;

end TB_ARCHITECTURE;

configuration TESTBENCH_FOR_chirp of chirp_tb is
	for TB_ARCHITECTURE
		for UUT : chirp
			use entity work.chirp(arch);
		end for;
	end for;
end TESTBENCH_FOR_chirp;

