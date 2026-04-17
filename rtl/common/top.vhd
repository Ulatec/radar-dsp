library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;


entity top is

  port (
    clk    : in std_logic; -- Clock signal
    reset  : in std_logic; -- Reset signal (active high)
    trigger : in std_logic; -- Trigger signal to start processing
    detection_tvalid : out std_logic; -- Valid signal indicating detection result is valid
    detection_tdata : out std_logic; -- Detection result (1-bit indicating detection)
    detection_tlast : out std_logic -- Last signal indicating the last sample of the output
  );
end entity top;

architecture arch of top is
  -- Between chirp and matched filter (16-bit I/Q)
  signal chirp_to_mf_tvalid  : std_logic;
  signal chirp_to_mf_tready  : std_logic;
  signal chirp_to_mf_tdata_i : signed(15 downto 0);
  signal chirp_to_mf_tdata_q : signed(15 downto 0);
  signal chirp_to_mf_tlast   : std_logic;

  -- Between matched filter and CFAR (32-bit I/Q)
  signal mf_to_cfar_tvalid  : std_logic;
  signal mf_to_cfar_tready  : std_logic;
  signal mf_to_cfar_tdata_i : signed(31 downto 0);
  signal mf_to_cfar_tdata_q : signed(31 downto 0);
  signal mf_to_cfar_tlast   : std_logic;
  signal detection_tready : std_logic := '1';
  component chirp is
	port (
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
	end component chirp;  
    component matched_filter is
        port (
            clk    : in std_logic; -- Clock signal
            reset  : in std_logic; -- Reset signal (active high)
    
            s_axis_tvalid : in std_logic; -- Valid signal for input data
            s_axis_tready : out std_logic; -- Ready signal for input data
            s_axis_tdata_i : in signed(15 downto 0); -- I component of input data
            s_axis_tdata_q : in signed(15 downto 0); -- Q component of input data
            s_axis_tlast : in std_logic; -- Last signal for input data
    
            m_axis_tvalid : out std_logic; -- Valid signal for output data
            m_axis_tready : in std_logic; -- Ready signal for output data
            m_axis_tdata_i : out signed(31 downto 0); -- Output data
            m_axis_tdata_q : out signed(31 downto 0); -- Output data
            m_axis_tlast : out std_logic -- Last signal for output data
        );
    end component matched_filter;
    component cfar_detector is
        port (
            clk    : in std_logic; -- Clock signal
            reset  : in std_logic; -- Reset signal (active high)
            s_axis_tvalid : in std_logic; -- Valid signal indicating input data is valid
            s_axis_tready : out std_logic; -- Ready signal indicating the module is ready to receive data
            s_axis_tdata_i  : in signed(31 downto 0); -- Input data (16-bit signed)
            s_axis_tdata_q  : in signed(31 downto 0); -- Input data (32-bit signed)
            s_axis_tlast  : in std_logic; -- Last signal indicating the last sample of
            m_axis_tvalid : out std_logic; -- Valid signal indicating output data is valid
            m_axis_tready : in std_logic; -- Ready signal indicating downstream is ready to receive data
            m_axis_tdata  : out std_logic; -- Output data (1-bit indicating detection)
            m_axis_tlast  : out std_logic -- Last signal indicating the last sample of the output
        );
    end component cfar_detector;




begin
     theChirp: chirp
        port map (
            clk => clk,
            reset => reset,
            start => trigger,
            done => open,
            busy => open,
            i_out => chirp_to_mf_tdata_i,
            q_out => chirp_to_mf_tdata_q,
            tvalid => chirp_to_mf_tvalid,
            tlast => chirp_to_mf_tlast,
            tready => chirp_to_mf_tready
        );
    theMatchedFilter: matched_filter
        port map (
            clk => clk,
            reset => reset,
            s_axis_tvalid => chirp_to_mf_tvalid,
            s_axis_tready => chirp_to_mf_tready,
            s_axis_tdata_i => chirp_to_mf_tdata_i,
            s_axis_tdata_q => chirp_to_mf_tdata_q,
            s_axis_tlast => chirp_to_mf_tlast,
            m_axis_tvalid => mf_to_cfar_tvalid,
            m_axis_tready => mf_to_cfar_tready,
            m_axis_tdata_i => mf_to_cfar_tdata_i,
            m_axis_tdata_q => mf_to_cfar_tdata_q,
            m_axis_tlast => mf_to_cfar_tlast
        );
    theCFAR: cfar_detector
        port map (
            clk => clk,
            reset => reset,
            s_axis_tvalid => mf_to_cfar_tvalid,
            s_axis_tready => mf_to_cfar_tready,
            s_axis_tdata_i => mf_to_cfar_tdata_i,
            s_axis_tdata_q => mf_to_cfar_tdata_q,
            s_axis_tlast => mf_to_cfar_tlast,
            m_axis_tvalid => detection_tvalid,
             m_axis_tready => detection_tready,
            m_axis_tdata => detection_tdata,
            m_axis_tlast => detection_tlast
        );
end architecture;