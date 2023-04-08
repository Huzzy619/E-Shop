from django.contrib import admin, messages
from django.db.models.aggregates import Count
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils.html import format_html, urlencode

from shop import models, forms

admin.site.register([models.Color, models.Size, models.Review])


class InventoryFilter(admin.SimpleListFilter):
    title = "inventory"
    parameter_name = "inventory"

    def lookups(self, request, model_admin):
        return [("<10", "Low")]

    def queryset(self, request, queryset: QuerySet):
        if self.value() == "<10":
            return queryset.filter(inventory__lt=10)


class ProductImageInline(admin.TabularInline):
    model = models.ProductImage
    readonly_fields = ["thumbnail"]
    min_num = 1
    max_num = 6
    extra = 1

    def thumbnail(self, instance):
        if instance.image.name != "":
            return format_html(f'<img src="{instance.image.url}" class="thumbnail" />')
        return ""




class ColorSizeInventoryInline(admin.TabularInline):
    model = models.ColorSizeInventory
    extra = 1




@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    autocomplete_fields = ["collection"]
    actions = ["clear_inventory"]
    form = forms.ProductForm
    inlines = [ProductImageInline,ColorSizeInventoryInline]
    list_display = ["title", "unit_price", "inventory_status", "collection_title"]
    list_editable = ["unit_price"]
    list_filter = ["collection", "last_update", InventoryFilter]
    list_per_page = 10
    list_select_related = ["collection"]
    search_fields = ["title"]

    def collection_title(self, product):
        return product.collection.title

    @admin.display(ordering="inventory")
    def inventory_status(self, product):
        if product.inventory < 10:
            return "Low"
        return "OK"

    @admin.action(description="Clear inventory")
    def clear_inventory(self, request, queryset):
        updated_count = queryset.update(inventory=0)
        self.message_user(
                request,
                f"{updated_count} products were successfully updated.",
                messages.ERROR,
        )
    

    # def save_model(self, request, obj, form:Form, change):
    #     if obj.is_digital and not obj.url:
    #         form.add_error('url', "A valid URL is required for a digital product")
    #         messages.set_level(request, messages.ERROR)
    #         messages.error(request, "Please fix the errors below.")
    #         return HttpResponseRedirect(reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.model_name), args=(obj.id,)))
    #     return super().save_model(request, obj, form, change)

    class Media:
        css = {"all": ["styles.css"]}



@admin.register(models.Collection)
class CollectionAdmin(admin.ModelAdmin):
    autocomplete_fields = ["featured_product"]
    list_display = ["title", "products_count"]
    search_fields = ["title"]

    @admin.display(ordering="products_count")
    def products_count(self, collection):
        url = (
                reverse("admin:shop_product_changelist")
                + "?"
                + urlencode({"collection__id": str(collection.id)})
        )
        return format_html(
                '<a href="{}">{} Products</a>', url, collection.products_count
        )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(products_count=Count("products"))


class OrderItemInline(admin.TabularInline):
    autocomplete_fields = ["product"]
    min_num = 1
    max_num = 10
    model = models.OrderItem
    extra = 0


@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ["id", "placed_at", "customer"]
    search_fields = ["payment_status", "customer"]


@admin.register(models.Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["type", "title", "general"]
    list_filter = ["type", "title", "general"]
    filter_horizontal = ("users",)






