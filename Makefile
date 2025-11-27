
.SUFFIXES:
.SUFFIXES: .o .f90 .F90 .f

MODEL = aermap.exe

FC = gfortran
FFLAGS  = -O2
LIBS    = 
INCLUDES =

DEFS   =



MODULES =\
	mod_main1.o\
	mod_tifftags.o\
	sub_calchc.o\
	sub_chkadj.o\
	sub_chkext.o\
	sub_cnrcnv.o\
	sub_demchk.o\
	sub_demrec.o\
	sub_demsrc.o\
	sub_domcnv.o\
	sub_initer_dem.o\
	sub_initer_ned.o\
	sub_nadcon.o\
	sub_nedchk.o\
	sub_read_tifftags.o\
	sub_reccnv.o\
	sub_recelv.o\
	sub_srccnv.o\
	sub_srcelv.o\
	sub_utmgeo.o

OBJS =\
	aermap.o

all:
	@$(MAKE) $(MODULES)
	@$(MAKE) $(MODEL)

$(MODEL): $(OBJS)
	$(FC) -o $(MODEL) $(FFLAGS) $(OBJS) $(MODULES) $(LIBS)

$(OBJS): $(MODULES)

.f90.o:
	$(FC) $(FFLAGS) $(INCLUDES) -c $<

.F90.o:
	$(FC) $(FFLAGS) $(INCLUDES) -c $< $(DEFS)

.f.o:
	$(FC) $(FFLAGS) $(INCLUDES) -c $< $(DEFS)

clean:
	rm -f *.o *.mod *.il $(MODEL)

