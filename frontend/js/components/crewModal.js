/**
 * Crew modal: the pals on one Activity card, for when there are too many to show inline
 * (an expedition auto-assigns a hundred). Opened with
 *   $dispatch('open-crew-modal', { title, subtitle, pals })
 * pals: [{ instance_id, name, level, image_candidates }]. Clicking one opens the pal modal on top.
 */
export function crewModal() {
    return {
        showCrewModal: false,
        crew: null,

        openCrewModal(detail) {
            this.crew = detail;
            this.showCrewModal = true;
        },

        closeCrewModal() {
            this.showCrewModal = false;
            setTimeout(() => { if (!this.showCrewModal) this.crew = null; }, 200);
        },
    };
}
