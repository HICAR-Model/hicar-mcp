!! Tiny fixture module for code-search / symbol tests.
module microphysics_driver
    implicit none
contains
    subroutine mp_init(options)
        ! initialize the microphysics scheme
        class(*), intent(in) :: options
    end subroutine mp_init

    subroutine mp_step(domain, dt)
        ! advance microphysics by one timestep
        class(*), intent(inout) :: domain
        real, intent(in) :: dt
    end subroutine mp_step
end module microphysics_driver
