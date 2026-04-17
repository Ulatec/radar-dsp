library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;
use work.sin_lut_pkg.all;


entity chirp is
  generic (
    SAMPLE_RATE : integer := 200_000; -- Sample rate in Hz
    F_START     : integer := 39_000; -- Start frequency of the chirp in Hz
    F_END       : integer := 41_000; -- End frequency of the chirp in Hz
    NUM_SAMPLES : integer := 64; -- Number of samples in the chirp
    PHASE_WIDTH : integer := 24 -- Phase accumulator width in bits
  );
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
end entity chirp;

architecture arch of chirp is
  type state_type is (IDLE, GEN);
  signal state                  : state_type                         := IDLE;
  signal sample_counter         : integer range 0 to NUM_SAMPLES - 1 := 0;
  signal phase_accumulator, fcw : unsigned(PHASE_WIDTH - 1 downto 0) := (others => '0');
  signal i_sample, q_sample     : signed(15 downto 0);
   
  -- Convert each frequency to an FCW value at elaboration time.
  -- FCW = (frequency * 2^PHASE_WIDTH) / sample_rate
  constant FCW_START : unsigned(PHASE_WIDTH - 1 downto 0) :=
  to_unsigned(integer(real(F_START) * (2.0 ** PHASE_WIDTH) / real(SAMPLE_RATE)), PHASE_WIDTH);

  constant FCW_END : unsigned(PHASE_WIDTH - 1 downto 0) :=
  to_unsigned(integer(real(F_END) * (2.0 ** PHASE_WIDTH) / real(SAMPLE_RATE)), PHASE_WIDTH);

  constant FCW_STEP : unsigned(PHASE_WIDTH - 1 downto 0) :=
  to_unsigned((to_integer(FCW_END) - to_integer(FCW_START)) / (NUM_SAMPLES - 1), PHASE_WIDTH);
begin
    i_sample <= SIN_TABLE((to_integer(phase_accumulator(PHASE_WIDTH-1 downto PHASE_WIDTH-LUT_INDEX_BITS)) + LUT_QUARTER)mod LUT_SIZE );
  q_sample <= SIN_TABLE(to_integer(phase_accumulator(PHASE_WIDTH-1 downto PHASE_WIDTH-LUT_INDEX_BITS))) ;
  process (clk, reset)
  begin

    if reset = '1' then
        state <= IDLE;
        sample_counter <= 0;
        phase_accumulator <= (others => '0');
        i_out <= (others => '0');
        q_out <= (others => '0');
        tvalid <= '0';
        tlast <= '0';
        done <= '0';
        busy <= '0';
    elsif rising_edge(clk) then
        case state is
            when IDLE =>
                done <= '0';
                tvalid <= '0';
                tlast <= '0';
                if start = '1' then
                    state <= GEN;
                    sample_counter <= 0;
                    phase_accumulator <= (others => '0');
                    fcw <= FCW_START;
                    busy <= '1';
                end if;
            when GEN =>
                if tready = '1' then
                    -- Output the current sample
                    i_out <= i_sample;
                    q_out <= q_sample;
                    tvalid <= '1';
                    if sample_counter = NUM_SAMPLES - 1 then
                        tlast <= '1';
                        state <= IDLE;
                        done <= '1';
                        busy <= '0';
                    else
                        tlast <= '0';
                        sample_counter <= sample_counter + 1;
                        phase_accumulator <= phase_accumulator + fcw;
                        fcw <= fcw + FCW_STEP;
                    end if;
                end if;

        end case;
    end if;

  end process;
end architecture;