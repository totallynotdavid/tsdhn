FC = ifx
FFLAGS = -O -parallel
OUT = .

all: $(OUT)/deform $(OUT)/fault_plane $(OUT)/tsunami

$(OUT)/deform: def_oka.f
	$(FC) $(FFLAGS) def_oka.f -o $@

$(OUT)/fault_plane: fault_plane.f90 physical_constants.inc
	$(FC) $(FFLAGS) fault_plane.f90 -o $@

$(OUT)/tsunami: tsunami1.for physical_constants.inc
	$(FC) $(FFLAGS) -qopenmp tsunami1.for -o $@

.PHONY: all
