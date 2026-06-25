!! Trimmed fixture mirroring HICAR's namelist /block/ declarations.
submodule(options_interface) options_implementation
contains
    module subroutine read_general(this)
        class(options_t), intent(inout) :: this
        namelist /general/    debug, nests, start_date
    end subroutine

    module subroutine read_physics(this)
        class(options_t), intent(inout) :: this
        namelist /physics/ mp, pbl, lsm
    end subroutine

    module subroutine read_output(this)
        class(options_t), intent(inout) :: this
        namelist /output/ outputinterval, output_vars
    end subroutine
end submodule
