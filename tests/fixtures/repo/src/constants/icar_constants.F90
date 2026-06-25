!>------------------------------------------------
!! Trimmed fixture mirroring HICAR's icar_constants.F90 formats.
!!------------------------------------------------
module icar_constants
    implicit none

    character(len=*), parameter :: kVERSION_STRING = "v9.9-fixture"
    integer, parameter :: kMAX_NESTS = 10
    integer, parameter :: kMAX_NAME_LENGTH = 1024

    ! Microphysics scheme codes
    integer, parameter :: kMP_THOMPSON = 1
    integer, parameter :: kMP_MORRISON = 3
    integer, parameter :: kMP_WSM6     = 4

    ! PBL scheme codes
    integer, parameter :: kPBL_YSU     = 1

    type var_constants_type
        SEQUENCE
        integer :: u, v, w
        integer :: pressure
        integer :: potential_temperature
        integer :: last_var
    end type var_constants_type

end module icar_constants
