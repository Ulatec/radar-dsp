library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;
use work.mf_coef_pkg.all;

entity matched_filter is
  generic (

    OUT_WIDTH : integer := 32; -- Bit width of the output samples
    SAMPLE_WIDTH : integer := 16; -- Bit width of the input samples
    NUM_TAPS : integer := 64 -- Number of taps in the filter
  );
  port (
    clk    : in std_logic; -- Clock signal
    reset  : in std_logic; -- Reset signal (active high)

    s_axis_tvalid : in std_logic; -- Valid signal for input data
    s_axis_tready : out std_logic; -- Ready signal for input data
    s_axis_tdata_i : in signed(SAMPLE_WIDTH - 1 downto 0); -- I component of input data
    s_axis_tdata_q : in signed(SAMPLE_WIDTH - 1 downto 0); -- Q component of input data
    s_axis_tlast : in std_logic; -- Last signal for input data

    m_axis_tvalid : out std_logic; -- Valid signal for output data
    m_axis_tready : in std_logic; -- Ready signal for output data
    m_axis_tdata_i : out signed(OUT_WIDTH - 1 downto 0); -- Output data
    m_axis_tdata_q : out signed(OUT_WIDTH - 1 downto 0); -- Output data
    m_axis_tlast : out std_logic -- Last signal for output data
  );
end entity matched_filter;

architecture arch of matched_filter is
    type state_type is (IDLE, LOAD, MAC, OUTPUT);
    type sample_buffer_type is array (0 to NUM_TAPS - 1) of signed(SAMPLE_WIDTH - 1 downto 0); -- Buffer to hold input samples for convolution
    signal sample_buffer_i, sample_buffer_q : sample_buffer_type := (others => (others => '0')); -- Buffers for I and Q components
    signal state : state_type := IDLE;
    signal tap_counter : integer range 0 to NUM_TAPS - 1 := 0;
    signal accum_real, accum_imag : signed(47 downto 0);
    signal last_flag : std_logic := '0';
    signal latched_i, latched_q : signed(SAMPLE_WIDTH - 1 downto 0);
begin

process(clk, reset)
begin
   
    if reset = '1' then
        state <= IDLE;
        sample_buffer_i <= (others => (others => '0'));
        sample_buffer_q <= (others => (others => '0'));
        tap_counter <= 0;
        accum_real <= (others => '0');
        accum_imag <= (others => '0');
        last_flag <= '0';
        s_axis_tready <= '1'; -- Ready to accept data
        m_axis_tvalid <= '0';
        m_axis_tdata_i <= (others => '0');
        m_axis_tdata_q <= (others => '0');
        m_axis_tlast <= '0';
    elsif rising_edge(clk) then
        case state is
            when IDLE =>
                s_axis_tready <= '1'; -- Ready to accept data
                m_axis_tvalid <= '0';
                if s_axis_tvalid = '1' then
                    latched_i <= s_axis_tdata_i;
                    latched_q <= s_axis_tdata_q;
                    last_flag <= s_axis_tlast;
                    state <= LOAD;
                    tap_counter <= 0;
                    accum_real <= (others => '0');
                    accum_imag <= (others => '0');
                    s_axis_tready <= '0'; -- Not ready while processing
                     -- Capture the last signal for output
                end if;
            when LOAD =>
                    for k in NUM_TAPS - 1 downto 1 loop
                        sample_buffer_i(k) <= sample_buffer_i(k - 1);
                        sample_buffer_q(k) <= sample_buffer_q(k - 1);
                     end loop;
                    sample_buffer_i(0) <= latched_i;
                    sample_buffer_q(0) <= latched_q;
                    state <= MAC;
            when MAC =>
                    accum_real <= accum_real + resize((sample_buffer_i(tap_counter) * (COEF_I(tap_counter))), 48) - resize((sample_buffer_q(tap_counter) * (COEF_Q(tap_counter))), 48);
                    accum_imag <= accum_imag + resize((sample_buffer_i(tap_counter) * (COEF_Q(tap_counter))), 48) + resize((sample_buffer_q(tap_counter) * (COEF_I(tap_counter))), 48);
                    if tap_counter = NUM_TAPS - 1 then
                        state <= OUTPUT;
                    else
                        tap_counter <= tap_counter + 1;
                    end if;
            when OUTPUT =>
                m_axis_tvalid <= '1';
                m_axis_tdata_i <= accum_real(47 downto 48 - OUT_WIDTH);
                m_axis_tdata_q <= accum_imag(47 downto 48 - OUT_WIDTH);
                m_axis_tlast <= last_flag;
                --if m_axis_tready = '1' then
                state <= IDLE;
               --     m_axis_tvalid <= '0';
                --end if;
            end case;
    end if;
end process;
    

end architecture;