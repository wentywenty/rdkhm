# SPDX-License-Identifier: GPL-2.0
# Keep generated configuration in the kernel output tree.
obj-$(CONFIG_DRIVERS_HDF) += hdf_hcs_hex.o
targets += hdf_hcs_hex.c
quiet_cmd_hcs = HCS     $@
      cmd_hcs = $(RDKHM_HC_GEN) -b -i -a -o $(obj)/hdf_hcs $(srctree)/$(src)/hdf.hcs

$(obj)/hdf_hcs_hex.c: $(src)/hdf.hcs $(RDKHM_HC_GEN) FORCE
	$(call if_changed,hcs)
