!! Trimmed fixture mirroring HICAR's namelist_utilities.F90 metadata routines.
module namelist_utilities
    use icar_constants
    implicit none
contains

    subroutine write_group_header(group, nml_unit)
        character(len=*), intent(in) :: group
        integer, intent(in) :: nml_unit
        select case (group)
            case ("General")
                write(nml_unit,*) "&general"
            case ("Physics")
                write(nml_unit,*) "&physics"
            case ("Output")
                write(nml_unit,*) "&output"
        end select
    end subroutine write_group_header

    subroutine get_nml_var_metadata(name, group, description, default, min, max, type, values, units, dimensions, val_keys)
        character(len=*), intent(in) :: name
        character(len=*), intent(out) :: group, description, default, units
        character(len=*), allocatable, intent(out) :: dimensions(:)
        real,    intent(out) :: min, max
        integer, intent(out) :: type
        integer, allocatable, intent(out) :: values(:)
        character(len=*), allocatable, optional, intent(out) :: val_keys(:)

        group = ""
        description = ""
        default = ""
        units = ""
        type = 0
        min = 0
        max = 0
        select case (name)
            case ("debug")
                description = "Debugging flag (T/F)"
                default = ".False."
                group = "General"
            case ("nests")
                description = "Number of nests to use in the simulation"
                default = "1"
                min = 1
                max = kMAX_NESTS
                group = "General"
                type = 1
            case ("start_date")
                description = "Start date for simulation, format: 'YYYY-MM-DD HH:MM:SS'"
                default = ""
                group = "General"
            case ("mp")
                description = "Microphysics scheme to use: "//achar(10)//BLNK_CHR_N// &
                                                          "'none'     = no MP,"//achar(10)//BLNK_CHR_N// &
                                                          "'Thompson' = Thompson et al (2008),"//achar(10)//BLNK_CHR_N// &
                                                          "'Morrison' = Morrison"//achar(10)//BLNK_CHR_N// &
                                                          "'WSM6'     = WSM6 (NOT SUPPORTED)"
                default = "none"
                if (present(val_keys)) then
                    val_keys = [character(len=kMAX_NAME_LENGTH) :: "none", "0", "thompson", trim(str(kMP_THOMPSON)), "morrison", trim(str(kMP_MORRISON)), "wsm6", trim(str(kMP_WSM6))]
                endif
                group = "Physics"
                type = 1
            case ("outputinterval")
                description = "Output interval in seconds"
                default = "3600"
                min = 1
                group = "Output"
        end select
    end subroutine get_nml_var_metadata

end module namelist_utilities
