"""Template tags used to sort a queryset.
"""

from django import template
from django.http import Http404
from django.conf import settings

register = template.Library()

DEFAULT_SORT_UP = getattr(settings, 'DEFAULT_SORT_UP' , '&uarr;')
DEFAULT_SORT_DOWN = getattr(settings, 'DEFAULT_SORT_DOWN' , '&darr;')
INVALID_FIELD_RAISES_404 = getattr(settings, 
        'SORTING_INVALID_FIELD_RAISES_404' , False)

sort_directions = {
    'asc': {'icon':DEFAULT_SORT_UP, 'inverse': 'desc'}, 
    'desc': {'icon':DEFAULT_SORT_DOWN, 'inverse': 'asc'}, 
    '': {'icon':DEFAULT_SORT_DOWN, 'inverse': 'asc'}, 
}


def anchor(parser, token):
    """
    Parses a tag that's supposed to be in this format:
    {% anchor field title anchor_class anchor_rel %}
    where the 'title', 'anchor_class' and 'anchor_rel' arguments are optional.
    """
    bits = [b.strip('"\'') for b in token.split_contents()]
    if len(bits) < 2:
        raise template.TemplateSyntaxError(
            "anchor tag takes at least 1 argument")
    try:
        title = bits[2]
    except IndexError:
        title = bits[1].capitalize()
    if len(bits) >= 4:
        # User specified the anchor_class and anchor_rel arguments
        anchor_class = bits[len(bits)-2]
        anchor_rel = bits[len(bits)-1]
        return SortAnchorNode(bits[1].strip(), title.strip(),
                              anchor_class.strip(), anchor_rel.strip())
    return SortAnchorNode(bits[1].strip(), title.strip())


class SortAnchorNode(template.Node):
    """
    Renders an <a> HTML tag with a link which href attribute 
    includes the field on which we sort and the direction.
    and adds an up or down arrow if the field is the one 
    currently being sorted on.

    Eg.
        {% anchor name Name %} generates
        <a href="/the/current/path/?sort=name" title="Name">Name</a>

    """
    def __init__(self, field, title, anchor_class=None, anchor_rel=None):
        self.field = field
        self.title = title
        self.anchor_class = ""
        self.anchor_rel = ""
        if anchor_class is not None:
            self.anchor_class = ' class="%s"' % anchor_class
        if anchor_rel is not None:
            self.anchor_rel = ' rel="%s"' % anchor_rel

    def render(self, context):
        request = context['request']
        getvars = request.GET.copy()
        if 'sort' in getvars:
            sortby = getvars['sort']
            del getvars['sort']
        else:
            sortby = ''
        if 'dir' in getvars:
            sortdir = getvars['dir']
            del getvars['dir']
        else:
            sortdir = ''
        if sortby == self.field:
            getvars['dir'] = sort_directions[sortdir]['inverse']
            icon = sort_directions[sortdir]['icon']
        else:
            icon = ''
        if len(getvars.keys()) > 0:
            urlappend = "&%s" % getvars.urlencode()
        else:
            urlappend = ''
        if icon:
            title = "%s %s" % (self.title, icon)
        else:
            title = self.title

        url = '%s?sort=%s%s' % (request.path, self.field, urlappend)
        return '<a href="%s" title="%s"%s%s>%s</a>' \
               % (url, self.title, self.anchor_class, self.anchor_rel, title)


def autosort(parser, token):
    bits = [b.strip('"\'') for b in token.split_contents()]
    if len(bits) != 2:
        raise template.TemplateSyntaxError(
            "autosort tag takes ecxactly one argument")
    return SortedDataNode(bits[1])

def attribute_lookup_factory(order_by):
    '''Returns function with django-db-like attribute lookup.
    Example: 
    '''
    keys = order_by.split('__')

    def attribute_lookup(obj):
        parent_obj = obj
        attr_obj = None
        
        for key in keys:
            # lookup parameters order:
            # 1. dictionary lookup
            # 2. method call
            # 3. attribute
            if hasattr(parent_obj, '__iter__'):
                if key in parent_obj:
                    attr_obj = parent_obj[key]
                    parent_obj = attr_obj
            elif hasattr(parent_obj, key):
                attr_obj = getattr(parent_obj, key)
                if hasattr(attr_obj, '__call__'):
                    if not getattr(attr_obj, 'alters_data', False):
                        parent_obj = attr_obj()
                else:
                    parent_obj = attr_obj
            else:
                break
        return parent_obj

    return attribute_lookup


class SortedDataNode(template.Node):
    """
    Automatically sort a queryset with {% autosort queryset %}
    """
    def __init__(self, queryset_var, context_var=None):
        self.queryset_var = template.Variable(queryset_var)
        self.context_var = context_var

    def render(self, context):
        key = self.queryset_var.var
        value = self.queryset_var.resolve(context)
        order_by = context['request'].field
        if len(order_by) > 1:
            try:
                context[key] = value.order_by(order_by)
            except AttributeError:
                if order_by[0] == '-':
                    reverse = True
                    order_by = order_by[1:]
                else:
                    reverse = False
                context[key] = sorted(value, key=attribute_lookup_factory(order_by),
                    reverse=reverse)
            except template.TemplateSyntaxError:
                if INVALID_FIELD_RAISES_404:
                    raise Http404(
                        'Invalid field sorting. If DEBUG were set to False, '
                        'an HTTP 404 page would have been shown instead.')
                context[key] = value
        else:
            context[key] = value
        return u''


def anchor(context, field, title, anchor_class=None, anchor_rel=None):
    request = context['request']
    getvars = request.GET.copy()
    if 'sort' in getvars:
        sortby = getvars['sort']
        del getvars['sort']
    else:
        sortby = ''
    if 'dir' in getvars:
        sortdir = getvars['dir']
        del getvars['dir']
    else:
        sortdir = ''
    if sortby == field:
        getvars['dir'] = sort_directions[sortdir]['inverse']
        icon = sort_directions[sortdir]['icon']
    else:
        icon = ''
    if len(getvars.keys()) > 0:
        urlappend = "&%s" % getvars.urlencode()
    else:
        urlappend = ''
    reverse = sort_directions[sortdir]['inverse']

    url = '%s?sort=%s%s' % (request.path, field, urlappend)
    return {
        'url': url,
        'title': title,
        'icon': icon,
        'inverse_icon': '' if icon == '' else sort_directions[reverse]['icon'],
        'class': anchor_class,
        'rel': anchor_rel,
        'urlappend': urlappend,
        'sortdir': sortdir,
    }

anchor = register.tag(anchor)
autosort = register.tag(autosort)
register.inclusion_tag('django_sorting/anchor.html', takes_context=True)(anchor)
