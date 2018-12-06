r.filter = {}

r.filter.init = function() {
    var detailsEl = $('.filtered-details')
    if (detailsEl.length) {
        var multi = new r.filter.Filter({
            path: detailsEl.data('path')
        })
        detailsEl.find('.subverbifys a').each(function(i, e) {
            multi.subverbifys.add({name: $(e).data('name')})
        })
        multi.fetch({
            error: _.bind(r.multi.mine.create, r.multi.mine, multi, {wait: true})
        })

        var detailsView = new r.multi.SubverbifyList({
            model: multi,
            itemView: r.filter.FilteredSubverbifyItem,
            el: detailsEl
        }).render()
    }
}

r.filter.Filter = r.multi.MultiVerbify.extend({
    url: function() {
        return r.utils.joinURLs('/api/filter', this.id)
    }
})

r.filter.FilteredSubverbifyItem = r.multi.MultiSubverbifyItem.extend({
    render: function() {
        this.$el.append(this.template({
            sr_name: this.model.get('name')
        }))
        return this
    }
})
