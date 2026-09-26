/**
 * Item popup: the picture big, the description, and what the tables know about it. Opened from any
 * item tile (partials/item-icon.html, partials/inv-slot.html) with
 *   $dispatch('open-item-modal', { item })
 * where item is the tile's object (item_id, item_name, icon, rarity, count, schematic, ...). The tile
 * data draws at once; /api/items/<id> fills in the description and is cached for the session.
 */
import { api } from '../services/api.js';

const cache = new Map();

export function itemModal() {
    return {
        showItemModal: false,
        item: null,       // the tile as clicked (count, note, slot ...)
        detail: null,     // /api/items/<id>
        detailFailed: false,

        async openItemModal(detail) {
            const item = detail && detail.item;
            if (!item || !item.item_id) return;
            this.item = item;
            this.detail = cache.get(item.item_id) || null;
            this.detailFailed = false;
            this.showItemModal = true;
            if (this.detail) return;
            try {
                const info = await api.getItem(item.item_id);
                cache.set(item.item_id, info);
                if (this.item && this.item.item_id === item.item_id) this.detail = info;
            } catch (e) {
                if (this.item && this.item.item_id === item.item_id) this.detailFailed = true;
            }
        },

        closeItemModal() {
            this.showItemModal = false;
            setTimeout(() => { if (!this.showItemModal) { this.item = null; this.detail = null; } }, 200);
        },

        get itemName() { return (this.detail && this.detail.name) || (this.item && this.item.item_name) || ''; },
        get itemIcon() { return (this.detail && this.detail.icon) || (this.item && this.item.icon) || null; },
        get itemRarity() {
            const r = this.detail ? this.detail.rarity : (this.item && this.item.rarity);
            return (r === 0 || r) ? r : null;
        },
        get itemSchematic() { return (this.detail && this.detail.schematic) || (this.item && this.item.schematic) || null; },
        get gearStats() {
            const g = (this.detail && this.detail.gear) || {};
            return [['hp', 'HP'], ['defense', 'Defense'], ['shield', 'Shield']]
                .filter(([k]) => g[k])
                .map(([k, label]) => ({ label, value: g[k] }));
        },
    };
}
