!! Trimmed fixture mirroring HICAR's get_varmeta branches.
module default_output_metadata
contains
    function get_varmeta(var_idx, opt, forcing_var, force_boundaries) result(var_meta)
        integer, intent(in) :: var_idx
        type(meta_data_t) :: var_meta

        if (var_idx==kVARS%u) then
            var_meta%name        = "u"
            var_meta%maxval      = 1000.0
            var_meta%minval      = -1000.0
            var_meta%dimensions  = three_d_u_t_dimensions
            var_meta%attributes  = [attribute_t("standard_name", "eastward_wind"),          &
                               attribute_t("long_name",     "Grid relative eastward wind"), &
                               attribute_t("units",         "m s-1")]
            if (present(opt) .and. present(forcing_var)) forcing_var = (opt%forcing%uvar /= "")
        else if (var_idx==kVARS%pressure) then
            var_meta%name        = "pressure"
            var_meta%maxval      = 110000.0
            var_meta%minval      = 0.0
            var_meta%dimensions  = three_d_t_dimensions
            var_meta%attributes  = [attribute_t("standard_name", "air_pressure"),  &
                               attribute_t("long_name",     "Pressure"),           &
                               attribute_t("units",         "Pa")]
            if (present(opt) .and. present(forcing_var)) forcing_var = (opt%forcing%pvar /= "")
        end if
    end function get_varmeta
end module default_output_metadata
