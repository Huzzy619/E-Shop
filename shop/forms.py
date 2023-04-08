from django import forms
from . import models
class ProductForm(forms.ModelForm):

    class Meta:
        model = models.Product
        fields = "__all__"
    
    def clean(self):
        cleaned_data =  super().clean()

        if cleaned_data.get("is_digital", "") and not cleaned_data.get("url", ""):
            raise forms.ValidationError("A valid URL is required for a digital product")
    
        return cleaned_data