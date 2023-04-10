import string, random

def id_generator(Model, chars=string.digits + string.ascii_uppercase):
        length = Model._meta.get_field("id").max_length
        value = "".join(random.choice(chars) for _ in range(length -1))
        while Model.objects.filter(id=value):
            value = "".join(random.choice(chars) for _ in range(length -1))

        return "#" + value