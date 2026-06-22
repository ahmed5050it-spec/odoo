from odoo import models, fields, api


class PCFCategory(models.Model):
    _name = 'pcf.category'
    _description = 'APQC Process Classification Framework Category'
    _order = 'code'

    code = fields.Char(required=True, unique=True, help='Category code (e.g., 1.0, 2.0)')
    name = fields.Char(required=True)
    description = fields.Text()
    metrics_available = fields.Boolean(help='Whether metrics are available for this category')
    difference_index = fields.Integer(help='Change index from previous PCF version')
    change_details = fields.Text(help='Details of changes from previous version')

    # Parent reference for hierarchy
    parent_id = fields.Many2one('pcf.category', string='Parent Category', ondelete='cascade')
    child_ids = fields.One2many('pcf.category', 'parent_id', string='Sub-Categories')

    # Level in hierarchy
    hierarchy_level = fields.Integer(compute='_compute_hierarchy_level', store=True)

    # Relationships
    process_ids = fields.One2many('pcf.process', 'category_id', string='Detailed Processes')
    activity_mapping_ids = fields.One2many('pcf.activity.mapping', 'pcf_category_id',
                                          string='Activity Mappings')

    @api.depends('parent_id', 'parent_id.hierarchy_level')
    def _compute_hierarchy_level(self):
        for record in self:
            if not record.parent_id:
                record.hierarchy_level = 0
            else:
                record.hierarchy_level = record.parent_id.hierarchy_level + 1

    def name_get(self):
        result = []
        for record in self:
            indent = '  ' * record.hierarchy_level
            name = f'{indent}{record.code} - {record.name}'
            result.append((record.id, name))
        return result


class PCFProcess(models.Model):
    _name = 'pcf.process'
    _description = 'APQC PCF Detailed Process'
    _order = 'pcf_id'

    pcf_id = fields.Integer(required=True, unique=True, help='APQC PCF process ID')
    hierarchy_id = fields.Char(required=True, help='Hierarchy ID (e.g., 1.1.1.1)')
    name = fields.Char(required=True)
    description = fields.Text()

    category_id = fields.Many2one('pcf.category', required=True, ondelete='cascade',
                                 string='PCF Category')

    # Process Details
    difference_index = fields.Integer(help='Change from previous version')
    change_details = fields.Text(help='What changed in this version')
    metrics_available = fields.Boolean(help='Metrics available for this process?')

    # Hierarchy
    parent_id = fields.Many2one('pcf.process', string='Parent Process', ondelete='cascade')
    child_ids = fields.One2many('pcf.process', 'parent_id', string='Sub-Processes')
    hierarchy_level = fields.Integer(compute='_compute_hierarchy_level', store=True)

    # Relationships
    activity_mapping_ids = fields.One2many('pcf.activity.mapping', 'pcf_process_id',
                                          string='Activity Mappings')

    @api.depends('parent_id', 'parent_id.hierarchy_level')
    def _compute_hierarchy_level(self):
        for record in self:
            if not record.parent_id:
                record.hierarchy_level = 0
            else:
                record.hierarchy_level = record.parent_id.hierarchy_level + 1

    def name_get(self):
        result = []
        for record in self:
            indent = '  ' * record.hierarchy_level
            name = f'{indent}{record.hierarchy_id} - {record.name}'
            result.append((record.id, name))
        return result
