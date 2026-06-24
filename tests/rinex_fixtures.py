"""Synthetic RINEX / GAMIT-output fixtures for the unit tests.

Everything is generated in-memory with carefully placed fixed-width columns so
the tests do not depend on network access, CDDIS credentials, or a GAMIT
installation.
"""


def _hdr(content, label):
    """A 80-col RINEX header record: <=60-col content + label at col 60."""
    return content.ljust(60)[:60] + label + "\n"


# Column-correct RINEX 3.04 observation header with GPS (6 obs) + GLONASS (4 obs).
RINEX3_HEADER = (
    _hdr("     3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE")
    + _hdr("CAS1", "MARKER NAME")
    + _hdr("66011M001", "MARKER NUMBER")
    + _hdr("OBS                 AGENCY", "OBSERVER / AGENCY")
    + _hdr("3001234             SEPT POLARX5        5.3.2", "REC # / TYPE / VERS")
    + _hdr("ANT5678             SEPCHOKE_B3E6   SPKE", "ANT # / TYPE")
    + _hdr("  -901376.0000 2409388.0000-5816613.0000", "APPROX POSITION XYZ")
    + _hdr("        0.0083        0.0000        0.0000", "ANTENNA: DELTA H/E/N")
    + _hdr("G    6 C1C L1C D1C S1C C2W L2W", "SYS / # / OBS TYPES")
    + _hdr("R    4 C1C L1C C2C L2C", "SYS / # / OBS TYPES")
    + _hdr("    30.000", "INTERVAL")
    + _hdr("  2025     1     1     0     0    0.0000000     GPS", "TIME OF FIRST OBS")
    + _hdr("  2025     1     1    23    59   30.0000000     GPS", "TIME OF LAST OBS")
    + _hdr("", "END OF HEADER")
)


def _obs(width_fields):
    """Concatenate observation value fields, each 16 chars (14.3 + LLI + SSI)."""
    return "".join(f"{v:>14}  " for v in width_fields)


def rinex3_file(num_epochs=2):
    """Return a complete RINEX 3 observation file as a string.

    Each epoch has one GPS satellite (G05) and one GLONASS satellite (R01).
    """
    lines = [RINEX3_HEADER]
    for k in range(num_epochs):
        minute = k  # distinct epochs
        epoch = (">" + " 2025 01 01 00 "
                 + f"{minute:02d}" + "  0.0000000" + "  0" + "  2")
        lines.append(epoch + "\n")
        # G05: 6 obs values
        lines.append("G05" + _obs(["20000000.000", "105000000.00",
                                    "2000.000", "45.000",
                                    "20000005.000", "81000000.000"]) + "\n")
        # R01: 4 obs values (dropped by GPS-only conversion)
        lines.append("R01" + _obs(["21000000.000", "112000000.00",
                                    "21000005.000", "87000000.000"]) + "\n")
    return "".join(lines)


# A minimal RINEX 2.11 file (used to test the converter pass-through path).
RINEX2_FILE = (
    _hdr("     2.11           OBSERVATION DATA    G", "RINEX VERSION / TYPE")
    + _hdr("CAS1", "MARKER NAME")
    + _hdr("     2    C1    L1", "# / TYPES OF OBSERV")
    + _hdr("", "END OF HEADER")
    + " 25  1  1  0  0  0.0000000  0  1G05\n"
    + "  20000000.000  105000000.00\n"
)


# ---- GAMIT output fixtures -------------------------------------------------

# o-file with ATMZEN (daily mean + one segment), GEOC coordinates.
OFILE = (
    "   13*CAS1 ATMZEN  m           2.2655438832-0.1066D-01 0.5965D-02  -1.8       2.25488495\n"
    "   17*CAS1 ATMZEN  m   1       0.0000000000-0.2437D-01 0.1142D-01  -2.1      -0.02436935\n"
    "    1*CAS1 GEOC LAT  dms    S66:08:28.75542 0.1971D-02 0.2461D-01  0.1  S66:08:28.75536\n"
    "    2*CAS1 GEOC LONG dms   E110:31:10.94427-0.2388D-02 0.2465D-01 -0.1 E110:31:10.94408\n"
    "    3*CAS1 RADIUS    km     6360.2587609893-0.2210D-02 0.2822D-01 -0.1  6360.25875878\n"
    " Double-difference observations: 6110\n"
    " Total parameters: 268 167\n"
)

# sh_gamit summary file.
SUMMARY = (
    " Prefit nrms:  0.41331E+00    Postfit nrms: 0.23542E+00\n"
    " Phase ambiguities (Total  WL-fixed   NL-fixed): 89 87 76\n"
    " Phase ambiguities WL fixed  97.8% NL fixed  85.4%\n"
)

# q-file (SOLVE output) with no companion sh_gamit summary: the quality
# metrics must be recovered from here. Mimics the real layout where several
# Prefit/Postfit nrms blocks appear (constrained/loose, bias-free/fixed); the
# parser takes the first pair as representative.
QFILE = (
    "          Program SOLVE Version 10.71\n"
    "   59 Phase ambiguities in solution\n"
    "   58 WL ambiguities resolved by AUTCLN\n"
    " Prefit nrms:  0.77653E+00    Postfit nrms: 0.23629E+00\n"
    "   40 NL ambiguities resolved\n"
    " Prefit nrms:  0.77451E+00    Postfit nrms: 0.25216E+00\n"
    " Double-difference observations: 7766\n"
    " Total parameters: 184 69\n"
)

# A *preliminary* o-file (suffix 'p') that must be ignored in favour of the
# final 'a' solution when both are present in a session directory.
OFILE_PREFIT = (
    "   13*CAS1 ATMZEN  m           9.9999999999-0.1066D-01 0.5965D-02  -1.8       9.99999999\n"
    " Double-difference observations: 1111\n"
)
