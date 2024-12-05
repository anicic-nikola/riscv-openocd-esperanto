# SPDX-License-Identifier: GPL-2.0-or-later

noinst_LTLIBRARIES += %D%/libriscv.la
%C%_libriscv_la_LIBADD =

if RISCV

.PHONY: riscv-transport-message
riscv-transport-message:
	@echo "Adding RISV transport lib"

check-riscv-lib:
	@if test -f "%D%/transport/libocdriscvtransport.la"; then \
		echo "RISC-V transport library found."; \
	else \
		echo "Warning: RISC-V transport library not found at %D%/transport/libocdriscvtransport.la"; \
        exit 1; \
	fi
       
all-local: riscv-transport-message check-riscv-lib
include %D%/transport/Makefile.am
%C%_libriscv_la_LIBADD += $(top_builddir)/%D%/transport/libocdriscvtransport.la
endif

%C%_libriscv_la_SOURCES = \
       %D%/asm.h \
       %D%/batch.h \
       %D%/debug_defines.h \
       %D%/debug_reg_printer.h \
       %D%/encoding.h \
       %D%/gdb_regs.h \
       %D%/opcodes.h \
       %D%/program.h \
       %D%/riscv.h \
       %D%/riscv-011.h \
       %D%/riscv-011_reg.h \
       %D%/riscv-013.h \
       %D%/riscv-013_reg.h \
       %D%/batch.c \
       %D%/program.c \
       %D%/riscv-011.c \
       %D%/riscv-011_reg.c \
       %D%/riscv-013.c \
       %D%/riscv-013_reg.c \
       %D%/riscv.c \
       %D%/riscv_reg.c \
       %D%/riscv_semihosting.c \
       %D%/debug_defines.c \
       %D%/debug_reg_printer.c

STARTUP_TCL_SRCS += %D%/startup.tcl
