library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;

entity cfar_detector is
  generic (
    INPUT_WIDTH : integer := 32; -- Sample rate in Hz
    NUM_TRAIN     : integer := 64; -- Start frequency of the chirp in Hz
    NUM_GUARD       : integer := 32; -- End frequency of the chirp in Hz
    ALPHA_Q : integer := 3949; -- Number of samples in the chirp\
    INPUT_SHIFT : integer := 12 -- Number of bits to shift input data to align with fixed-point representation
  );
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
end entity cfar_detector;

architecture arch of cfar_detector is
    constant WINDOW_SIZE : integer := 2*(NUM_TRAIN + NUM_GUARD) + 1; -- Total size of the sliding window
    constant MAG_WIDTH : integer := 40; -- Width of the magnitude calculation (input width + shift)
    constant SUM_WIDTH : integer := 48;
    constant PROD_WIDTH : integer := 68; 

    type mag_buffer_type is array (0 to WINDOW_SIZE - 1) of unsigned(MAG_WIDTH - 1 downto 0);
    signal mag_buffer : mag_buffer_type := (others => (others => '0')); -- Buffer to hold magnitudes
    signal  sum_left, sum_right : unsigned(SUM_WIDTH - 1 downto 0) := (others => '0'); -- Sums of left and right training cells
    signal warmup_counter : integer range 0 to WINDOW_SIZE - 1 := 0; -- Counter to track warm-up period
    signal window_full : std_logic := '0'; -- Signal indicating the sliding window is full
    
    
begin
   
    process(clk, reset)
    variable shifted_i : signed(31 - INPUT_SHIFT downto 0);
    variable shifted_q : signed(31 - INPUT_SHIFT downto 0);
    variable new_mag : unsigned(MAG_WIDTH - 1 downto 0);
    variable threshold : unsigned(PROD_WIDTH - 1 downto 0);
    begin
        if reset = '1' then
            mag_buffer <= (others => (others => '0'));
            sum_left <= (others => '0');
            sum_right <= (others => '0');
            warmup_counter <= 0;
            window_full <= '0';
            s_axis_tready <= '1';
            m_axis_tvalid <= '0';
            m_axis_tdata <= '0';
            m_axis_tlast <= '0';
        elsif rising_edge(clk) then
            if(s_axis_tvalid = '1') then
                m_axis_tlast <= s_axis_tlast;
                shifted_i := s_axis_tdata_i(31 downto INPUT_SHIFT); -- Shift input to align with fixed-point representation
                shifted_q := s_axis_tdata_q(31 downto INPUT_SHIFT); -- Shift input to align with fixed-point representation
                new_mag := resize (unsigned(shifted_i * shifted_i) + unsigned(shifted_q * shifted_q), MAG_WIDTH); -- Calculate magnitude and resize to fit MAG_WIDTH
                sum_right <= sum_right + new_mag - mag_buffer(NUM_TRAIN - 1); -- Update right sum by adding new magnitude and removing the oldest magnitude
                sum_left <= sum_left + mag_buffer((NUM_TRAIN + (NUM_GUARD*2))) - mag_buffer(WINDOW_SIZE - 1);
                for k in WINDOW_SIZE - 1 downto 1 loop
                        mag_buffer(k) <= mag_buffer(k - 1);
                end loop;
                    mag_buffer(0) <= new_mag;
                    if warmup_counter = WINDOW_SIZE -1 then
                        window_full <= '1';
                    else
                        warmup_counter <= warmup_counter + 1;
                    end if;
                    if window_full = '1' then 
                        m_axis_tvalid <= '1';
                        threshold := resize((sum_left + sum_right) * to_unsigned(ALPHA_Q, 32) srl 16, PROD_WIDTH); -- Calculate threshold by multiplying total sum with scaling factor ALPHA_Q
                        if resize(mag_buffer(NUM_TRAIN + NUM_GUARD - 1), PROD_WIDTH) > threshold then
                            m_axis_tdata <= '1'; -- Set output to 1 if the cell under test exceeds the threshold
                        else
                            m_axis_tdata <= '0'; -- Set output to 0 otherwise
                        end if;
                    else
                        m_axis_tvalid <= '1';
                        m_axis_tdata <= '0'; -- Output 0 during warm-up period
                    end if;
                end if;
        end if;
    end process;

end architecture;